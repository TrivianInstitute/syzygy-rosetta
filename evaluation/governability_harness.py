"""Continuing Governability Challenge Suite for Syzygy Rosetta 2.1.

The suite distinguishes architectural readiness from demonstrated continuing
causal authority. It does not claim that passing these reference scenarios
establishes real-world governability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum
from typing import Dict, Optional

from core.authority import (
    AuthorityGrant,
    grant_authority,
    revoke_authority,
    validate_authority,
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
    """Reference decision function for a consequential action.

    Decision order is intentionally fail-closed:

    1. unresolved ambiguity requires clarification;
    2. invalid authority blocks execution;
    3. valid correction inside the intervention window alters the path;
    4. correction after the declared boundary is surfaced as too late;
    5. only then may execution proceed.
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


def run_reference_challenge_suite() -> Dict[str, GovernabilityResult]:
    """Run deterministic reference scenarios for the five primary failure modes.

    These scenarios verify the reference semantics only. They do not test live
    agents, transport guarantees, distributed clocks, external side effects,
    consent legitimacy, or independent causal validity.
    """

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


if __name__ == "__main__":
    assert_reference_challenge_suite()
    for scenario_name, result in run_reference_challenge_suite().items():
        print(f"{scenario_name}: {result.decision.value} ({result.reason})")
