"""Continuing Governability Challenge Suite for Syzygy Rosetta 2.1.

The suite distinguishes architectural readiness from demonstrated continuing
causal authority. It does not claim that passing these reference scenarios
establishes real-world governability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum
from typing import Dict, Optional

from core.authority import (
    AuthorityGrant,
    AuthorityRegistry,
    AuthorityStatus,
    QueuedAuthorityReference,
    grant_authority,
    queue_authority_reference,
    revoke_authority,
    validate_authority,
    validate_queued_authority,
)
from core.execution_boundary import (
    ExecutionBoundary,
    ExecutionStage,
    can_correction_still_change_outcome,
)


class EvidenceLevel(IntEnum):
    PROPOSED = 0
    IMPLEMENTED = 1
    UNIT_TESTED = 2
    SIMULATED = 3
    INTEGRATION_TESTED = 4
    LIVE_OBSERVED = 5
    INDEPENDENTLY_REPLICATED = 6


class GovernabilityDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    CLARIFY = "clarify"
    INTERVENE = "intervene"
    INTERVENTION_TOO_LATE = "intervention_too_late"


class FrozenAdjudication(str, Enum):
    FAIL = "FAIL"
    SURVIVES = "SURVIVES"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class GovernabilityEvidence:
    claim: str
    scenario: str
    decision: GovernabilityDecision
    evidence_level: EvidenceLevel
    authority_valid: Optional[bool]
    consequence_changed: Optional[bool]
    notes: str = ""


@dataclass(frozen=True)
class GovernabilityResult:
    decision: GovernabilityDecision
    reason: str
    evidence: GovernabilityEvidence


@dataclass(frozen=True)
class QueuedExecutionTrace:
    """Audit trace for authority resolution at consequential release."""

    authority_id: str
    queued_authority_version: int
    queued_authority_status: str
    queued_authority_scope: tuple[str, ...]
    current_authority_resolved: bool
    current_authority_version: Optional[int]
    current_authority_status: Optional[str]
    current_authority_scope: tuple[str, ...]
    stale_snapshot_detected: Optional[bool]
    last_reversible_boundary: str
    release_stage: str
    final_decision: str
    reason: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class QueuedGovernabilityResult:
    decision: GovernabilityDecision
    reason: str
    evidence: GovernabilityEvidence
    trace: QueuedExecutionTrace


@dataclass(frozen=True)
class FrozenFalsifierResult:
    adjudication: FrozenAdjudication
    result: QueuedGovernabilityResult


def evaluate_governability(
    grant: AuthorityGrant,
    action: str,
    boundary: ExecutionBoundary,
    current_stage: ExecutionStage,
    *,
    now: Optional[datetime] = None,
    current_state_digest: Optional[str] = None,
    correction_requested: bool = False,
    ambiguous_context: bool = False,
    scenario: str = "unspecified",
    evidence_level: EvidenceLevel = EvidenceLevel.IMPLEMENTED,
) -> GovernabilityResult:
    """Reference decision function for an unqueued consequential action.

    This function validates the supplied grant object. It remains useful for
    immediate/nonqueued evaluation. A queued action must instead use
    :func:`evaluate_queued_governability`, which requires authoritative current
    resolution before release.
    """

    if ambiguous_context:
        evidence = GovernabilityEvidence(
            claim="Ambiguous consequential authority must not be silently resolved.",
            scenario=scenario,
            decision=GovernabilityDecision.CLARIFY,
            evidence_level=evidence_level,
            authority_valid=None,
            consequence_changed=True,
            notes="Execution withheld pending clarification.",
        )
        return GovernabilityResult(
            GovernabilityDecision.CLARIFY,
            "ambiguous_context_requires_clarification",
            evidence,
        )

    authority = validate_authority(
        grant,
        action,
        now=now,
        current_state_digest=current_state_digest,
    )
    if not authority.valid:
        evidence = GovernabilityEvidence(
            claim="Invalid authority must not remain causally effective.",
            scenario=scenario,
            decision=GovernabilityDecision.BLOCK,
            evidence_level=evidence_level,
            authority_valid=False,
            consequence_changed=True,
            notes=authority.reason,
        )
        return GovernabilityResult(
            GovernabilityDecision.BLOCK,
            authority.reason,
            evidence,
        )

    if correction_requested:
        if can_correction_still_change_outcome(boundary, current_stage):
            evidence = GovernabilityEvidence(
                claim="Legitimate correction remains effective through the declared boundary.",
                scenario=scenario,
                decision=GovernabilityDecision.INTERVENE,
                evidence_level=evidence_level,
                authority_valid=True,
                consequence_changed=True,
                notes=f"Correction accepted at {current_stage.name}.",
            )
            return GovernabilityResult(
                GovernabilityDecision.INTERVENE,
                "correction_causally_effective",
                evidence,
            )

        evidence = GovernabilityEvidence(
            claim="The system must disclose when correction arrives after the last alterable boundary.",
            scenario=scenario,
            decision=GovernabilityDecision.INTERVENTION_TOO_LATE,
            evidence_level=evidence_level,
            authority_valid=True,
            consequence_changed=False,
            notes=(
                f"Correction arrived at {current_stage.name}; last correctable stage was "
                f"{boundary.last_correctable_stage.name}."
            ),
        )
        return GovernabilityResult(
            GovernabilityDecision.INTERVENTION_TOO_LATE,
            "past_last_correctable_boundary",
            evidence,
        )

    evidence = GovernabilityEvidence(
        claim="Current, scoped authority permits execution when no unresolved correction exists.",
        scenario=scenario,
        decision=GovernabilityDecision.ALLOW,
        evidence_level=evidence_level,
        authority_valid=True,
        consequence_changed=False,
        notes="Reference pre-execution checks passed.",
    )
    return GovernabilityResult(
        GovernabilityDecision.ALLOW,
        "authority_current_and_action_in_scope",
        evidence,
    )


def _queued_trace(
    reference: QueuedAuthorityReference,
    validation,
    boundary: ExecutionBoundary,
    current_stage: ExecutionStage,
    decision: GovernabilityDecision,
    reason: str,
) -> QueuedExecutionTrace:
    current = validation.resolution.current_grant
    return QueuedExecutionTrace(
        authority_id=reference.authority_id,
        queued_authority_version=reference.queued_version,
        queued_authority_status=reference.queued_status.value,
        queued_authority_scope=tuple(sorted(reference.queued_scope)),
        current_authority_resolved=validation.resolution.resolved,
        current_authority_version=current.version if current is not None else None,
        current_authority_status=current.status.value if current is not None else None,
        current_authority_scope=tuple(sorted(current.scope)) if current is not None else (),
        stale_snapshot_detected=(
            validation.resolution.stale_snapshot
            if current is not None
            else None
        ),
        last_reversible_boundary=boundary.last_correctable_stage.name,
        release_stage=current_stage.name,
        final_decision=decision.value,
        reason=reason,
    )


def evaluate_queued_governability(
    registry: AuthorityRegistry,
    reference: QueuedAuthorityReference,
    action: str,
    boundary: ExecutionBoundary,
    current_stage: ExecutionStage,
    *,
    now: Optional[datetime] = None,
    current_state_digest: Optional[str] = None,
    correction_requested: bool = False,
    ambiguous_context: bool = False,
    scenario: str = "queued_execution",
    evidence_level: EvidenceLevel = EvidenceLevel.IMPLEMENTED,
) -> QueuedGovernabilityResult:
    """Evaluate queued consequential work using current authority, never snapshot authority."""

    if ambiguous_context:
        # Ambiguity itself is sufficient to withhold consequence. We still try
        # current resolution for the audit trace, but never convert ambiguity
        # into authority.
        validation = validate_queued_authority(
            registry,
            reference,
            action,
            now=now,
            current_state_digest=current_state_digest,
        )
        decision = GovernabilityDecision.CLARIFY
        reason = "ambiguous_context_requires_clarification"
        evidence = GovernabilityEvidence(
            claim="Ambiguous queued consequential authority must not be silently resolved.",
            scenario=scenario,
            decision=decision,
            evidence_level=evidence_level,
            authority_valid=(validation.valid if validation.resolution.resolved else None),
            consequence_changed=True,
            notes="Execution withheld pending clarification.",
        )
        return QueuedGovernabilityResult(
            decision,
            reason,
            evidence,
            _queued_trace(reference, validation, boundary, current_stage, decision, reason),
        )

    validation = validate_queued_authority(
        registry,
        reference,
        action,
        now=now,
        current_state_digest=current_state_digest,
    )
    if not validation.valid:
        decision = GovernabilityDecision.BLOCK
        reason = validation.reason
        evidence = GovernabilityEvidence(
            claim="Queued consequence requires authoritative current authority resolution.",
            scenario=scenario,
            decision=decision,
            evidence_level=evidence_level,
            authority_valid=False if validation.resolution.resolved else None,
            consequence_changed=True,
            notes=reason,
        )
        return QueuedGovernabilityResult(
            decision,
            reason,
            evidence,
            _queued_trace(reference, validation, boundary, current_stage, decision, reason),
        )

    if correction_requested:
        if can_correction_still_change_outcome(boundary, current_stage):
            decision = GovernabilityDecision.INTERVENE
            reason = "correction_causally_effective"
            evidence = GovernabilityEvidence(
                claim="Legitimate correction remains effective through the declared boundary.",
                scenario=scenario,
                decision=decision,
                evidence_level=evidence_level,
                authority_valid=True,
                consequence_changed=True,
                notes=f"Correction accepted at {current_stage.name}.",
            )
        else:
            decision = GovernabilityDecision.INTERVENTION_TOO_LATE
            reason = "past_last_correctable_boundary"
            evidence = GovernabilityEvidence(
                claim="The system must disclose when correction arrives after the last alterable boundary.",
                scenario=scenario,
                decision=decision,
                evidence_level=evidence_level,
                authority_valid=True,
                consequence_changed=False,
                notes=(
                    f"Correction arrived at {current_stage.name}; last correctable stage was "
                    f"{boundary.last_correctable_stage.name}."
                ),
            )
        return QueuedGovernabilityResult(
            decision,
            reason,
            evidence,
            _queued_trace(reference, validation, boundary, current_stage, decision, reason),
        )

    decision = GovernabilityDecision.ALLOW
    reason = validation.reason
    evidence = GovernabilityEvidence(
        claim="Queued execution is governed by the current resolved authority version.",
        scenario=scenario,
        decision=decision,
        evidence_level=evidence_level,
        authority_valid=True,
        consequence_changed=False,
        notes=reason,
    )
    return QueuedGovernabilityResult(
        decision,
        reason,
        evidence,
        _queued_trace(reference, validation, boundary, current_stage, decision, reason),
    )


def run_frozen_stale_authority_falsifier() -> FrozenFalsifierResult:
    """Run the externally frozen T0-T3 stale-authority sequence unchanged.

    T0: authority is active.
    T1: an action is queued while holding that authority.
    T2: the authority is revoked.
    T3: the queued action is released for execution.

    The queued historical snapshot is retained for provenance but cannot govern
    the T3 decision. The canonical registry must resolve current authority.
    """

    t0 = datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    t2 = t0 + timedelta(minutes=2)
    t3 = t0 + timedelta(minutes=3)

    registry = AuthorityRegistry()
    active = registry.register(
        grant_authority(
            "frozen-authority-1",
            "reference-agent",
            {"execute"},
            issued_at=t0,
            expires_at=t0 + timedelta(hours=1),
        )
    )

    # T1 — queue while v1 is active. The timestamp is intentionally retained in
    # the frozen sequence even though the compact reference does not require it.
    _ = t1
    queued = queue_authority_reference(active)

    # T2 — revocation creates and registers current v2.
    _ = t2
    registry.revoke(active.authority_id)

    # T3 — release at the last reversible boundary. Current authority must be
    # re-resolved before consequence.
    boundary = ExecutionBoundary(
        action_id="frozen-queued-action",
        last_correctable_stage=ExecutionStage.DISPATCHED,
    )
    result = evaluate_queued_governability(
        registry,
        queued,
        "execute",
        boundary,
        ExecutionStage.DISPATCHED,
        now=t3,
        scenario="frozen_t0_t3_stale_authority",
        evidence_level=EvidenceLevel.UNIT_TESTED,
    )

    current_status = result.trace.current_authority_status
    if not result.trace.current_authority_resolved:
        adjudication = FrozenAdjudication.UNRESOLVED
    elif current_status == AuthorityStatus.REVOKED.value and result.decision is GovernabilityDecision.BLOCK:
        adjudication = FrozenAdjudication.SURVIVES
    elif result.decision is GovernabilityDecision.ALLOW:
        adjudication = FrozenAdjudication.FAIL
    else:
        # The authority state was resolved, but the outcome does not match the
        # frozen expected semantics. Treat that as a failure, not uncertainty.
        adjudication = FrozenAdjudication.FAIL

    return FrozenFalsifierResult(adjudication, result)


def run_reference_challenge_suite() -> Dict[str, GovernabilityResult]:
    """Run deterministic reference scenarios for the original failure modes."""

    now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    boundary = ExecutionBoundary(
        action_id="reference-action",
        last_correctable_stage=ExecutionStage.DISPATCHED,
    )

    current = grant_authority(
        "authority-current",
        "reference-agent",
        {"execute"},
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=30),
    )
    state_bound = grant_authority(
        "authority-state-bound",
        "reference-agent",
        {"execute"},
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=30),
        state_digest="state:v1",
    )

    return {
        "baseline": evaluate_governability(
            current,
            "execute",
            boundary,
            ExecutionStage.QUEUED,
            now=now,
            scenario="baseline",
            evidence_level=EvidenceLevel.SIMULATED,
        ),
        "changed_reality": evaluate_governability(
            state_bound,
            "execute",
            boundary,
            ExecutionStage.QUEUED,
            now=now,
            current_state_digest="state:v2",
            scenario="changed_reality",
            evidence_level=EvidenceLevel.SIMULATED,
        ),
        "stale_state": evaluate_governability(
            state_bound,
            "execute",
            boundary,
            ExecutionStage.QUEUED,
            now=now,
            current_state_digest=None,
            scenario="stale_state",
            evidence_level=EvidenceLevel.SIMULATED,
        ),
        "revocation": evaluate_governability(
            revoke_authority(current),
            "execute",
            boundary,
            ExecutionStage.QUEUED,
            now=now,
            scenario="revocation",
            evidence_level=EvidenceLevel.SIMULATED,
        ),
        "ambiguity": evaluate_governability(
            current,
            "execute",
            boundary,
            ExecutionStage.QUEUED,
            now=now,
            ambiguous_context=True,
            scenario="ambiguity",
            evidence_level=EvidenceLevel.SIMULATED,
        ),
        "delay_before_boundary": evaluate_governability(
            current,
            "execute",
            boundary,
            ExecutionStage.DISPATCHED,
            now=now,
            correction_requested=True,
            scenario="delay_before_boundary",
            evidence_level=EvidenceLevel.SIMULATED,
        ),
        "delay_after_boundary": evaluate_governability(
            current,
            "execute",
            boundary,
            ExecutionStage.COMMITTED,
            now=now,
            correction_requested=True,
            scenario="delay_after_boundary",
            evidence_level=EvidenceLevel.SIMULATED,
        ),
    }


def assert_reference_challenge_suite() -> None:
    """Raise AssertionError if reference semantics regress."""

    results = run_reference_challenge_suite()
    expected = {
        "baseline": GovernabilityDecision.ALLOW,
        "changed_reality": GovernabilityDecision.BLOCK,
        "stale_state": GovernabilityDecision.BLOCK,
        "revocation": GovernabilityDecision.BLOCK,
        "ambiguity": GovernabilityDecision.CLARIFY,
        "delay_before_boundary": GovernabilityDecision.INTERVENE,
        "delay_after_boundary": GovernabilityDecision.INTERVENTION_TOO_LATE,
    }
    for name, decision in expected.items():
        actual = results[name].decision
        if actual is not decision:
            raise AssertionError(f"{name}: expected {decision.value}, got {actual.value}")

    frozen = run_frozen_stale_authority_falsifier()
    if frozen.adjudication is not FrozenAdjudication.SURVIVES:
        raise AssertionError(
            "frozen stale-authority falsifier: expected SURVIVES, "
            f"got {frozen.adjudication.value}"
        )


if __name__ == "__main__":
    import json

    assert_reference_challenge_suite()
    for scenario_name, result in run_reference_challenge_suite().items():
        print(f"{scenario_name}: {result.decision.value} ({result.reason})")

    frozen = run_frozen_stale_authority_falsifier()
    print(f"frozen_t0_t3: {frozen.adjudication.value}")
    print(json.dumps(frozen.result.trace.as_dict(), indent=2, sort_keys=True))
