"""Authority lifecycle primitives for Syzygy Rosetta 2.1.

This module operationalizes a narrow question: is a grant of authority still
valid for a consequential action at the time of execution?

It is intentionally standalone and depends only on the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import FrozenSet, Iterable, Mapping, Optional


class AuthorityStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    INVALIDATED = "invalidated"


@dataclass(frozen=True)
class AuthorityGrant:
    """A scoped, time-bounded and optionally state-bound grant of authority."""

    authority_id: str
    subject: str
    scope: FrozenSet[str]
    issued_at: datetime
    expires_at: Optional[datetime] = None
    state_digest: Optional[str] = None
    status: AuthorityStatus = AuthorityStatus.ACTIVE
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.authority_id.strip():
            raise ValueError("authority_id must be non-empty")
        if not self.subject.strip():
            raise ValueError("subject must be non-empty")
        if not self.scope:
            raise ValueError("scope must contain at least one action")
        if self.issued_at.tzinfo is None:
            raise ValueError("issued_at must be timezone-aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at <= self.issued_at:
                raise ValueError("expires_at must be later than issued_at")


@dataclass(frozen=True)
class AuthorityValidation:
    valid: bool
    reason: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def grant_authority(
    authority_id: str,
    subject: str,
    scope: Iterable[str],
    *,
    issued_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    expires_in: Optional[timedelta] = None,
    state_digest: Optional[str] = None,
    metadata: Optional[Mapping[str, str]] = None,
) -> AuthorityGrant:
    """Create a new active grant.

    ``expires_at`` and ``expires_in`` are mutually exclusive. ``*`` may be used
    as a wildcard scope, but callers should prefer the narrowest practical scope.
    """

    if expires_at is not None and expires_in is not None:
        raise ValueError("provide expires_at or expires_in, not both")

    issued = issued_at or _utc_now()
    if expires_in is not None:
        if expires_in <= timedelta(0):
            raise ValueError("expires_in must be positive")
        expires_at = issued + expires_in

    normalized_scope = frozenset(item.strip() for item in scope if item.strip())
    return AuthorityGrant(
        authority_id=authority_id,
        subject=subject,
        scope=normalized_scope,
        issued_at=issued,
        expires_at=expires_at,
        state_digest=state_digest,
        status=AuthorityStatus.ACTIVE,
        metadata=dict(metadata or {}),
    )


def renew_authority(
    grant: AuthorityGrant,
    *,
    expires_at: datetime,
    renewed_at: Optional[datetime] = None,
    state_digest: Optional[str] = None,
) -> AuthorityGrant:
    """Renew an active grant without silently reviving revoked authority."""

    if grant.status is not AuthorityStatus.ACTIVE:
        raise ValueError("revoked or invalidated authority requires a new grant")

    renewed = renewed_at or _utc_now()
    if renewed.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("renewed_at and expires_at must be timezone-aware")
    if expires_at <= renewed:
        raise ValueError("expires_at must be later than renewed_at")

    return replace(
        grant,
        issued_at=renewed,
        expires_at=expires_at,
        state_digest=grant.state_digest if state_digest is None else state_digest,
    )


def limit_authority(grant: AuthorityGrant, scope: Iterable[str]) -> AuthorityGrant:
    """Narrow a grant. This function never expands existing authority."""

    requested = frozenset(item.strip() for item in scope if item.strip())
    if not requested:
        raise ValueError("limited scope must contain at least one action")

    if "*" not in grant.scope and not requested.issubset(grant.scope):
        raise ValueError("limited scope cannot expand the existing grant")

    return replace(grant, scope=requested)


def revoke_authority(grant: AuthorityGrant) -> AuthorityGrant:
    return replace(grant, status=AuthorityStatus.REVOKED)


def invalidate_authority(grant: AuthorityGrant) -> AuthorityGrant:
    return replace(grant, status=AuthorityStatus.INVALIDATED)


def validate_authority(
    grant: AuthorityGrant,
    action: str,
    *,
    now: Optional[datetime] = None,
    current_state_digest: Optional[str] = None,
) -> AuthorityValidation:
    """Validate authority immediately before consequential execution.

    Fail-closed semantics apply when a grant was bound to a state digest but the
    current state cannot be verified.
    """

    current_time = now or _utc_now()
    if current_time.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    if grant.status is AuthorityStatus.REVOKED:
        return AuthorityValidation(False, "authority_revoked")
    if grant.status is AuthorityStatus.INVALIDATED:
        return AuthorityValidation(False, "authority_invalidated")
    if current_time < grant.issued_at:
        return AuthorityValidation(False, "authority_not_yet_effective")
    if grant.expires_at is not None and current_time >= grant.expires_at:
        return AuthorityValidation(False, "authority_expired")
    if action not in grant.scope and "*" not in grant.scope:
        return AuthorityValidation(False, "action_out_of_scope")

    if grant.state_digest is not None:
        if current_state_digest is None:
            return AuthorityValidation(False, "state_unverified")
        if current_state_digest != grant.state_digest:
            return AuthorityValidation(False, "state_changed")

    return AuthorityValidation(True, "authority_valid")


def can_execute(
    grant: AuthorityGrant,
    action: str,
    *,
    now: Optional[datetime] = None,
    current_state_digest: Optional[str] = None,
) -> bool:
    return validate_authority(
        grant,
        action,
        now=now,
        current_state_digest=current_state_digest,
    ).valid
