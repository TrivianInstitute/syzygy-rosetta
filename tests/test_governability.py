from datetime import datetime, timedelta, timezone

import pytest

from core.authority import (
    AuthorityRegistry,
    can_execute,
    grant_authority,
    limit_authority,
    queue_authority_reference,
    renew_authority,
    revoke_authority,
    validate_authority,
    validate_queued_authority,
)
from core.execution_boundary import (
    ExecutionBoundary,
    ExecutionStage,
    can_correction_still_change_outcome,
)
from evaluation.governability_harness import (
    FrozenAdjudication,
    GovernabilityDecision,
    assert_reference_challenge_suite,
    evaluate_governability,
    evaluate_queued_governability,
    run_frozen_stale_authority_falsifier,
)


NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


def active_grant(**kwargs):
    params = {
        "authority_id": "a-1",
        "subject": "agent-1",
        "scope": {"send", "draft"},
        "issued_at": NOW - timedelta(minutes=5),
        "expires_at": NOW + timedelta(minutes=30),
    }
    params.update(kwargs)
    return grant_authority(**params)


def queued_boundary():
    return ExecutionBoundary("send-email", ExecutionStage.DISPATCHED)


def test_current_scoped_authority_can_execute():
    assert can_execute(active_grant(), "send", now=NOW)


def test_expired_authority_fails_closed():
    grant = active_grant(
        issued_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
    )
    result = validate_authority(grant, "send", now=NOW)
    assert not result.valid
    assert result.reason == "authority_expired"


def test_revoked_authority_cannot_execute():
    result = validate_authority(revoke_authority(active_grant()), "send", now=NOW)
    assert not result.valid
    assert result.reason == "authority_revoked"


def test_out_of_scope_action_is_blocked():
    result = validate_authority(active_grant(), "purchase", now=NOW)
    assert not result.valid
    assert result.reason == "action_out_of_scope"


def test_state_change_invalidates_state_bound_authority():
    grant = active_grant(state_digest="price:90")
    result = validate_authority(
        grant,
        "send",
        now=NOW,
        current_state_digest="price:135",
    )
    assert not result.valid
    assert result.reason == "state_changed"


def test_unverified_state_fails_closed():
    grant = active_grant(state_digest="state:v1")
    result = validate_authority(grant, "send", now=NOW)
    assert not result.valid
    assert result.reason == "state_unverified"


def test_limit_authority_cannot_expand_scope():
    narrowed = limit_authority(active_grant(), {"draft"})
    assert narrowed.scope == frozenset({"draft"})
    assert narrowed.version == 2
    with pytest.raises(ValueError):
        limit_authority(narrowed, {"draft", "send"})


def test_revoked_authority_cannot_be_silently_renewed():
    revoked = revoke_authority(active_grant())
    with pytest.raises(ValueError):
        renew_authority(
            revoked,
            renewed_at=NOW,
            expires_at=NOW + timedelta(hours=1),
        )


def test_execution_boundary_is_inclusive():
    boundary = queued_boundary()
    assert can_correction_still_change_outcome(boundary, ExecutionStage.DISPATCHED)
    assert not can_correction_still_change_outcome(boundary, ExecutionStage.COMMITTED)


def test_ambiguity_requires_clarification():
    result = evaluate_governability(
        active_grant(),
        "send",
        queued_boundary(),
        ExecutionStage.QUEUED,
        now=NOW,
        ambiguous_context=True,
    )
    assert result.decision is GovernabilityDecision.CLARIFY


def test_correction_before_boundary_intervenes():
    result = evaluate_governability(
        active_grant(),
        "send",
        queued_boundary(),
        ExecutionStage.DISPATCHED,
        now=NOW,
        correction_requested=True,
    )
    assert result.decision is GovernabilityDecision.INTERVENE
    assert result.evidence.consequence_changed is True


def test_correction_after_boundary_is_disclosed_as_too_late():
    result = evaluate_governability(
        active_grant(),
        "send",
        queued_boundary(),
        ExecutionStage.COMMITTED,
        now=NOW,
        correction_requested=True,
    )
    assert result.decision is GovernabilityDecision.INTERVENTION_TOO_LATE
    assert result.evidence.consequence_changed is False


# ---------------------------------------------------------------------------
# Externally frozen stale-authority audit
# ---------------------------------------------------------------------------


def test_prefx_failure_witness_historical_snapshot_remains_locally_valid():
    """Preserve the exact defect that motivated current-authority resolution.

    Before the repair, queued execution could simply validate the v1 object it
    retained. Revoking authority produced a separate immutable object, so the
    old object still validated. This assertion is historical evidence, not an
    approved queued-execution path.
    """

    active = active_grant()
    queued_snapshot = active
    revoked_current = revoke_authority(active)

    assert queued_snapshot.version == 1
    assert revoked_current.version == 2
    assert validate_authority(queued_snapshot, "send", now=NOW).valid is True
    assert validate_authority(revoked_current, "send", now=NOW).valid is False


def test_current_revoked_authority_blocks():
    """Current revoked authority is invalid regardless of queued provenance."""

    registry = AuthorityRegistry()
    current = registry.register(active_grant())
    registry.revoke(current.authority_id)
    revoked = registry.resolve(current.authority_id)

    result = validate_authority(revoked, "send", now=NOW)
    assert result.valid is False
    assert result.reason == "authority_revoked"


def test_stale_historical_authority_retained_by_queue_is_not_authoritative():
    """T1 v1 may remain in memory, but T3 must resolve current v2."""

    registry = AuthorityRegistry()
    active = registry.register(active_grant())
    queued = queue_authority_reference(active)
    registry.revoke(active.authority_id)

    result = evaluate_queued_governability(
        registry,
        queued,
        "send",
        queued_boundary(),
        ExecutionStage.DISPATCHED,
        now=NOW,
    )

    assert result.decision is GovernabilityDecision.BLOCK
    assert result.reason == "authority_revoked"
    assert result.trace.queued_authority_version == 1
    assert result.trace.current_authority_version == 2
    assert result.trace.stale_snapshot_detected is True


def test_changed_authority_version_is_reresolved_and_current_version_governs():
    """A newer still-valid version may authorize only after re-resolution."""

    registry = AuthorityRegistry()
    active = registry.register(active_grant())
    queued = queue_authority_reference(active)
    renewed = registry.renew(
        active.authority_id,
        renewed_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )

    result = evaluate_queued_governability(
        registry,
        queued,
        "send",
        queued_boundary(),
        ExecutionStage.DISPATCHED,
        now=NOW,
    )

    assert renewed.version == 2
    assert result.decision is GovernabilityDecision.ALLOW
    assert result.reason == "authority_reresolved_current_version"
    assert result.trace.queued_authority_version == 1
    assert result.trace.current_authority_version == 2
    assert result.trace.stale_snapshot_detected is True


def test_narrowed_current_authority_blocks_action_removed_from_scope():
    registry = AuthorityRegistry()
    active = registry.register(active_grant())
    queued = queue_authority_reference(active)
    narrowed = registry.limit(active.authority_id, {"draft"})

    result = evaluate_queued_governability(
        registry,
        queued,
        "send",
        queued_boundary(),
        ExecutionStage.DISPATCHED,
        now=NOW,
    )

    assert narrowed.version == 2
    assert narrowed.scope == frozenset({"draft"})
    assert result.decision is GovernabilityDecision.BLOCK
    assert result.reason == "action_out_of_scope"
    assert result.trace.current_authority_scope == ("draft",)


def test_missing_current_authority_fails_closed():
    """If current authority cannot be authoritatively resolved, do not execute."""

    queued = queue_authority_reference(active_grant())
    empty_registry = AuthorityRegistry()

    validation = validate_queued_authority(
        empty_registry,
        queued,
        "send",
        now=NOW,
    )
    result = evaluate_queued_governability(
        empty_registry,
        queued,
        "send",
        queued_boundary(),
        ExecutionStage.DISPATCHED,
        now=NOW,
    )

    assert validation.valid is False
    assert validation.reason == "current_authority_unresolvable"
    assert result.decision is GovernabilityDecision.BLOCK
    assert result.reason == "current_authority_unresolvable"
    assert result.trace.current_authority_resolved is False
    assert result.trace.current_authority_version is None


def test_valid_unchanged_authority_allows_queued_release():
    registry = AuthorityRegistry()
    active = registry.register(active_grant())
    queued = queue_authority_reference(active)

    result = evaluate_queued_governability(
        registry,
        queued,
        "send",
        queued_boundary(),
        ExecutionStage.DISPATCHED,
        now=NOW,
    )

    assert result.decision is GovernabilityDecision.ALLOW
    assert result.reason == "authority_current_and_valid"
    assert result.trace.queued_authority_version == 1
    assert result.trace.current_authority_version == 1
    assert result.trace.stale_snapshot_detected is False


def test_frozen_t0_t3_stale_authority_falsifier_survives_with_trace():
    frozen = run_frozen_stale_authority_falsifier()
    trace = frozen.result.trace

    assert frozen.adjudication is FrozenAdjudication.SURVIVES
    assert trace.authority_id == "frozen-authority-1"
    assert trace.queued_authority_version == 1
    assert trace.queued_authority_status == "active"
    assert trace.current_authority_version == 2
    assert trace.current_authority_status == "revoked"
    assert trace.stale_snapshot_detected is True
    assert trace.last_reversible_boundary == "DISPATCHED"
    assert trace.release_stage == "DISPATCHED"
    assert trace.final_decision == "block"
    assert trace.reason == "authority_revoked"


def test_reference_challenge_suite_semantics():
    assert_reference_challenge_suite()
