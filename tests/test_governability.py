from datetime import datetime, timedelta, timezone

import pytest

from core.authority import (
    can_execute,
    grant_authority,
    limit_authority,
    renew_authority,
    revoke_authority,
    validate_authority,
)
from core.execution_boundary import (
    ExecutionBoundary,
    ExecutionStage,
    can_correction_still_change_outcome,
)
from evaluation.governability_harness import (
    GovernabilityDecision,
    assert_reference_challenge_suite,
    evaluate_governability,
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
    boundary = ExecutionBoundary("send-email", ExecutionStage.DISPATCHED)
    assert can_correction_still_change_outcome(boundary, ExecutionStage.DISPATCHED)
    assert not can_correction_still_change_outcome(boundary, ExecutionStage.COMMITTED)


def test_ambiguity_requires_clarification():
    boundary = ExecutionBoundary("send-email", ExecutionStage.DISPATCHED)
    result = evaluate_governability(
        active_grant(),
        "send",
        boundary,
        ExecutionStage.QUEUED,
        now=NOW,
        ambiguous_context=True,
    )
    assert result.decision is GovernabilityDecision.CLARIFY


def test_correction_before_boundary_intervenes():
    boundary = ExecutionBoundary("send-email", ExecutionStage.DISPATCHED)
    result = evaluate_governability(
        active_grant(),
        "send",
        boundary,
        ExecutionStage.DISPATCHED,
        now=NOW,
        correction_requested=True,
    )
    assert result.decision is GovernabilityDecision.INTERVENE
    assert result.evidence.consequence_changed is True


def test_correction_after_boundary_is_disclosed_as_too_late():
    boundary = ExecutionBoundary("send-email", ExecutionStage.DISPATCHED)
    result = evaluate_governability(
        active_grant(),
        "send",
        boundary,
        ExecutionStage.COMMITTED,
        now=NOW,
        correction_requested=True,
    )
    assert result.decision is GovernabilityDecision.INTERVENTION_TOO_LATE
    assert result.evidence.consequence_changed is False


def test_reference_challenge_suite_semantics():
    assert_reference_challenge_suite()
