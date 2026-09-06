"""Authority lifecycle primitives for Syzygy Rosetta 2.1.

This module distinguishes two operations that must not be collapsed:

1. validating a particular immutable authority grant; and
2. resolving the current authoritative grant before a queued consequential
   action is released.

Queued execution must use the second path. A historical grant snapshot is
provenance, not continuing authority.

The implementation is intentionally standalone and depends only on the Python
standard library.
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
    """A versioned, scoped, time-bounded and optionally state-bound grant."""

    authority_id: str
    subject: str
    scope: FrozenSet[str]
    issued_at: datetime
    expires_at: Optional[datetime] = None
    state_digest: Optional[str] = None
    status: AuthorityStatus = AuthorityStatus.ACTIVE
    metadata: Mapping[str, str] = field(default_factory=dict)
    version: int = 1

    def __post_init__(self) -> None:
        if not self.authority_id.strip():
            raise ValueError("authority_id must be non-empty")
        if not self.subject.strip():
            raise ValueError("subject must be non-empty")
        if not self.scope:
            raise ValueError("scope must contain at least one action")
        if self.version < 1:
            raise ValueError("authority version must be >= 1")
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


@dataclass(frozen=True)
class QueuedAuthorityReference:
    """Authority provenance captured when an action enters a queue.

    This record never becomes authoritative merely because it was valid when
    queued. It exists so execution can compare the queued snapshot with the
    current authority resolved later.
    """

    authority_id: str
    queued_version: int
    queued_status: AuthorityStatus
    queued_scope: FrozenSet[str]
    queued_state_digest: Optional[str] = None


@dataclass(frozen=True)
class CurrentAuthorityResolution:
    """Result of resolving queued provenance against the canonical registry."""

    resolved: bool
    reason: str
    reference: QueuedAuthorityReference
    current_grant: Optional[AuthorityGrant] = None

    @property
    def stale_snapshot(self) -> bool:
        return (
            self.current_grant is not None
            and self.current_grant.version != self.reference.queued_version
        )


@dataclass(frozen=True)
class QueuedAuthorityValidation:
    """Validation result for a queued action at consequential release."""

    valid: bool
    reason: str
    resolution: CurrentAuthorityResolution
    current_validation: Optional[AuthorityValidation] = None


class AuthorityRegistry:
    """Canonical in-process authority store for standalone Rosetta.

    The registry owns the current grant for each ``authority_id``. Every
    lifecycle mutation advances the grant version. Queued actions store only a
    historical reference and must resolve through this registry before release.

    This is a reference architecture, not a distributed consensus system.
    Integrations may replace it with another authoritative store if they retain
    the same fail-closed current-resolution semantics.
    """

    def __init__(self) -> None:
        self._current: dict[str, AuthorityGrant] = {}

    def register(self, grant: AuthorityGrant) -> AuthorityGrant:
        existing = self._current.get(grant.authority_id)
        if existing is not None:
            if grant == existing:
                return existing
            if grant.version <= existing.version:
                raise ValueError("authority registry refuses version regression or overwrite")
        self._current[grant.authority_id] = grant
        return grant

    def resolve(self, authority_id: str) -> Optional[AuthorityGrant]:
        return self._current.get(authority_id)

    def renew(
        self,
        authority_id: str,
        *,
        expires_at: datetime,
        renewed_at: Optional[datetime] = None,
        state_digest: Optional[str] = None,
    ) -> AuthorityGrant:
        current = self._require_current(authority_id)
        updated = renew_authority(
            current,
            expires_at=expires_at,
            renewed_at=renewed_at,
            state_digest=state_digest,
        )
        self._current[authority_id] = updated
        return updated

    def limit(self, authority_id: str, scope: Iterable[str]) -> AuthorityGrant:
        current = self._require_current(authority_id)
        updated = limit_authority(current, scope)
        self._current[authority_id] = updated
        return updated

    def revoke(self, authority_id: str) -> AuthorityGrant:
        current = self._require_current(authority_id)
        updated = revoke_authority(current)
        self._current[authority_id] = updated
        return updated

    def invalidate(self, authority_id: str) -> AuthorityGrant:
        current = self._require_current(authority_id)
        updated = invalidate_authority(current)
        self._current[authority_id] = updated
        return updated

    def _require_current(self, authority_id: str) -> AuthorityGrant:
        current = self.resolve(authority_id)
        if current is None:
            raise KeyError(f"current authority not found: {authority_id}")
        return current


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
    version: int = 1,
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
        version=version,
    )


def renew_authority(
    grant: AuthorityGrant,
    *,
    expires_at: datetime,
    renewed_at: Optional[datetime] = None,
    state_digest: Optional[str] = None,
) -> AuthorityGrant:
    """Renew an active grant as a new immutable authority version."""

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
        version=grant.version + 1,
    )


def limit_authority(grant: AuthorityGrant, scope: Iterable[str]) -> AuthorityGrant:
    """Narrow a grant as a new immutable version. This never expands authority."""

    requested = frozenset(item.strip() for item in scope if item.strip())
    if not requested:
        raise ValueError("limited scope must contain at least one action")

    if "*" not in grant.scope and not requested.issubset(grant.scope):
        raise ValueError("limited scope cannot expand the existing grant")

    return replace(grant, scope=requested, version=grant.version + 1)


def revoke_authority(grant: AuthorityGrant) -> AuthorityGrant:
    return replace(
        grant,
        status=AuthorityStatus.REVOKED,
        version=grant.version + 1,
    )


def invalidate_authority(grant: AuthorityGrant) -> AuthorityGrant:
    return replace(
        grant,
        status=AuthorityStatus.INVALIDATED,
        version=grant.version + 1,
    )


def validate_authority(
    grant: AuthorityGrant,
    action: str,
    *,
    now: Optional[datetime] = None,
    current_state_digest: Optional[str] = None,
) -> AuthorityValidation:
    """Validate the supplied immutable grant.

    This function answers whether *this grant object* is valid. It does not prove
    that the object is still the current authority. Queued consequential actions
    must use :func:`validate_queued_authority`, which performs authoritative
    current resolution first.
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
    """Validate a specific grant object; not sufficient for queued release."""

    return validate_authority(
        grant,
        action,
        now=now,
        current_state_digest=current_state_digest,
    ).valid


def queue_authority_reference(grant: AuthorityGrant) -> QueuedAuthorityReference:
    """Capture the authority provenance held when an action is queued."""

    return QueuedAuthorityReference(
        authority_id=grant.authority_id,
        queued_version=grant.version,
        queued_status=grant.status,
        queued_scope=grant.scope,
        queued_state_digest=grant.state_digest,
    )


def resolve_current_authority(
    registry: AuthorityRegistry,
    reference: QueuedAuthorityReference,
) -> CurrentAuthorityResolution:
    """Resolve the current grant for a queued authority reference."""

    current = registry.resolve(reference.authority_id)
    if current is None:
        return CurrentAuthorityResolution(
            resolved=False,
            reason="current_authority_unresolvable",
            reference=reference,
            current_grant=None,
        )
    if current.version < reference.queued_version:
        return CurrentAuthorityResolution(
            resolved=False,
            reason="authority_version_regression",
            reference=reference,
            current_grant=current,
        )
    return CurrentAuthorityResolution(
        resolved=True,
        reason=(
            "current_authority_version_changed"
            if current.version != reference.queued_version
            else "current_authority_version_unchanged"
        ),
        reference=reference,
        current_grant=current,
    )


def validate_queued_authority(
    registry: AuthorityRegistry,
    reference: QueuedAuthorityReference,
    action: str,
    *,
    now: Optional[datetime] = None,
    current_state_digest: Optional[str] = None,
) -> QueuedAuthorityValidation:
    """Fail-closed current-authority validation for queued consequential work.

    A queued snapshot can never authorize execution on its own. The current
    authority must be resolved by ``authority_id`` and the resolved grant, not
    the queued grant, governs the decision.
    """

    resolution = resolve_current_authority(registry, reference)
    if not resolution.resolved or resolution.current_grant is None:
        return QueuedAuthorityValidation(
            valid=False,
            reason=resolution.reason,
            resolution=resolution,
            current_validation=None,
        )

    validation = validate_authority(
        resolution.current_grant,
        action,
        now=now,
        current_state_digest=current_state_digest,
    )
    if not validation.valid:
        return QueuedAuthorityValidation(
            valid=False,
            reason=validation.reason,
            resolution=resolution,
            current_validation=validation,
        )

    return QueuedAuthorityValidation(
        valid=True,
        reason=(
            "authority_reresolved_current_version"
            if resolution.stale_snapshot
            else "authority_current_and_valid"
        ),
        resolution=resolution,
        current_validation=validation,
    )
