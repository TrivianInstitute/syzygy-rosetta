# Continuing Governability Challenge Suite

**Syzygy Rosetta 2.1 extension**

The Continuing Governability Challenge Suite asks whether legitimate authority remains causally effective as a consequential action moves toward execution.

It is an additive test layer. It does **not** alter the Twelve Invariants, replace the Seven Vows, or make Rosetta dependent on the wider TRIA stack.

It also does not claim that a passing implementation has demonstrated continuing governability in real-world systems. The suite provides reference semantics, executable primitives, and falsification conditions that can be tested more rigorously in integrations, simulations, live deployments, and independent studies.

## Why this exists

Rosetta already treats autonomy, consent, transparency, uncertainty, reciprocity, and non-domination as normative requirements. Those principles are necessary but not sufficient to establish that authority can still change what a system actually does.

A system may correctly represent a user's wishes and still fail to preserve meaningful intervention if:

- authority has expired, narrowed, or been revoked;
- the state on which authority was granted has materially changed;
- the system cannot verify whether the state is still current;
- the instruction is ambiguous at the point of consequence;
- a correction arrives while intervention should still be possible but is not honored; or
- the system claims an action is still governable after the last boundary at which consequence can actually be changed.

This suite makes those conditions explicit.

## Four challenge questions

### 1. What establishes, renews, limits, or invalidates authority?

`core/authority.py` represents authority as a scoped lifecycle object rather than an implied property of a conversation.

An `AuthorityGrant` records:

- the authority identifier;
- the subject receiving authority;
- the permitted action scope;
- issuance and optional expiry time;
- optional binding to a specific state digest; and
- current status: active, revoked, or invalidated.

Reference operations include:

```python
grant_authority()
renew_authority()
limit_authority()
revoke_authority()
invalidate_authority()
validate_authority()
```

Validation is intended to occur immediately before consequential execution.

The reference implementation fails closed when a state-bound grant cannot be revalidated.

## 2. Where is the last boundary at which legitimate intervention can still alter consequence?

`core/execution_boundary.py` makes the correction window explicit.

The reference stages are:

```text
PROPOSED
AUTHORIZED
QUEUED
DISPATCHED
COMMITTED
IRREVERSIBLE
```

These are reference stages, not a universal ontology. Adapters and external systems may define different execution pipelines.

Each consequential action declares a `last_correctable_stage`. The boundary is inclusive: intervention at that stage is still considered causally effective; intervention after it is not.

```python
boundary = ExecutionBoundary(
    action_id="send-email",
    last_correctable_stage=ExecutionStage.DISPATCHED,
)

can_correction_still_change_outcome(
    boundary,
    ExecutionStage.DISPATCHED,
)  # True
```

The suite intentionally refuses to imply infinite reversibility. If a correction arrives after the declared boundary, the reference decision is `INTERVENTION_TOO_LATE`, not a false claim of continuing control.

## 3. What evidence distinguishes architectural readiness from demonstrated continuing governability?

`evaluation/governability_harness.py` defines an explicit evidence ladder:

| Level | Meaning |
|---|---|
| `PROPOSED` | theoretical or specified only |
| `IMPLEMENTED` | present in executable code |
| `UNIT_TESTED` | exercised by local tests |
| `SIMULATED` | exercised in deterministic or stochastic scenarios |
| `INTEGRATION_TESTED` | exercised across a real integration boundary |
| `LIVE_OBSERVED` | observed in a live deployment context |
| `INDEPENDENTLY_REPLICATED` | reproduced by an independent party |

These levels must not be collapsed.

A mechanism can be implemented and unit tested without establishing that it preserves legitimate authority under real latency, distributed state, external APIs, irreversible side effects, contested consent, adversarial conditions, or institutional constraints.

## 4. What falsifies continuing causal authority?

The reference suite targets five primary challenge conditions.

### Changed reality

Authority was granted under state `v1`; execution occurs under materially different state `v2`.

Expected reference behavior: **block and require revalidation**.

### Stale or unverifiable state

Authority is explicitly state-bound, but the current state cannot be verified.

Expected reference behavior: **fail closed**.

### Revocation

Authority is revoked before execution.

Expected reference behavior: **block**.

A revoked grant cannot be silently renewed. A new grant is required.

### Ambiguity

A consequential instruction can reasonably refer to more than one incompatible action or authority state.

Expected reference behavior: **clarify rather than silently choose**.

### Delay

A legitimate correction arrives while an action is moving through execution.

If the correction arrives at or before the declared last correctable boundary:

Expected reference behavior: **intervene and alter the path**.

If the correction arrives after that boundary:

Expected reference behavior: **disclose that intervention is too late**.

The second condition is not itself a failure of the architecture if the boundary was truthful and observable. A falsification occurs when a system claims intervention remains causally effective but fails to honor a legitimate correction received inside the declared correction window.

## Reference decision order

The harness uses deliberately conservative ordering:

```text
AMBIGUOUS?        -> CLARIFY
AUTHORITY INVALID?-> BLOCK
CORRECTION IN WINDOW? -> INTERVENE
CORRECTION TOO LATE?  -> DISCLOSE TOO LATE
OTHERWISE         -> ALLOW
```

This is a reference implementation, not an assertion that every domain should use identical stages or policy.

## Running the suite

Install Rosetta as usual and run:

```bash
python -m pytest -q
python -m evaluation.governability_harness
```

The harness includes deterministic reference scenarios for:

- baseline valid authority;
- changed reality;
- stale state;
- revocation;
- ambiguity;
- correction at the last valid boundary; and
- correction after the boundary.

## What passing does not establish

Passing these tests establishes only that the reference implementation behaves consistently with the declared challenge semantics.

It does not establish:

- that consent was legitimate or informed;
- that a state digest captures all relevant real-world change;
- that external systems will honor cancellation;
- that a declared boundary corresponds to the true physical or institutional point of irreversibility;
- that distributed systems will deliver corrections before deadlines;
- that human authority is always singular or uncontested;
- that every domain should fail closed in exactly the same way; or
- that continuing governability has been empirically validated.

Those remain research and integration questions.

## Relationship to the wider TRIA architecture

This suite is designed to remain useful when Rosetta is used alone.

When the wider TRIA stack is present, other components may enrich the inputs and evidence:

- Coheronmetry may provide relational-state observability;
- Orthogonal Signal may surface contested or divergent constraints;
- TRL may extend intervention and propagation questions across networks; and
- Diachronic Sovereignty may track changes in authority, memory, identity, and continuity across time.

None of those components is required by this reference implementation.

## Provenance and scope

This suite was prompted by independent review questions concerning authority lifecycle, intervention boundaries, evidence standards, and falsification under changed conditions. The implementation and terminology here are Rosetta-specific and deliberately avoid adopting or implying incorporation of any external proprietary or trademarked framework.

The purpose is not to make Rosetta harder to criticize. It is to make a central sovereignty claim harder to assert without executable evidence.
