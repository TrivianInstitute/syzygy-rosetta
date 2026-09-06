# Frozen Stale-Authority Falsifier — 2026-09-06

## Status

This record preserves the distinction between the pre-fix failure and the post-fix result. The frozen test sequence and adjudication were not changed by the repair.

## External falsifier

Frozen sequence:

- **T0** — authority is active.
- **T1** — an action is queued while holding that authority.
- **T2** — the authority is revoked.
- **T3** — the queued action is released for execution.

Frozen adjudication:

- **FAIL** — the queued action can still execute using the historical authority snapshot.
- **SURVIVES** — the action is forced to resolve current authority before consequence and current revocation stops execution.
- **UNRESOLVED** — it cannot be determined which authority state actually governed execution.

## Pre-fix baseline — FAIL

Baseline commit: `a1a7a76e215a7611126dce0305f057d28748f2c9` (merged Continuing Governability Challenge Suite, PR #9).

The baseline implementation correctly rejected a revoked `AuthorityGrant` when that revoked object was explicitly supplied to `validate_authority()`. However, authority lifecycle functions returned new immutable grant objects. `revoke_authority(active_v1)` therefore produced a distinct revoked object while the original active `v1` object remained unchanged.

The queued execution path had no canonical current-authority resolver. `evaluate_governability()` validated whichever `AuthorityGrant` object the caller supplied. Under the frozen sequence, a queue retaining the historical active object could therefore validate that historical object at T3 even though a newer revoked state existed elsewhere.

Pre-fix adjudication: **FAIL**.

This failure remains preserved by the regression witness `test_prefx_failure_witness_historical_snapshot_remains_locally_valid`. That test demonstrates the historical defect but is not an approved queued-execution path.

## Minimal repair

The repair remains standalone inside Syzygy Rosetta and uses only the Python standard library:

1. `AuthorityGrant` carries an immutable monotonically increasing `version`.
2. Renewal, narrowing, revocation, and invalidation create a new authority version.
3. `AuthorityRegistry` holds the canonical current grant for each `authority_id`.
4. Queued work captures a `QueuedAuthorityReference` containing historical provenance, not continuing authority.
5. `validate_queued_authority()` resolves the current grant from the registry before release.
6. Missing current authority, version regression, revoked/invalidated authority, expired authority, changed state, or current out-of-scope authority fail closed.
7. A changed but still-valid authority version may permit execution only after current re-resolution; the historical queued snapshot never authorizes by itself.
8. `evaluate_queued_governability()` is the reference queued-release gate and fails closed if first-time current-authority resolution is attempted after the declared last reversible boundary.

## Required regression cases

The test surface distinguishes:

- current revoked authority;
- stale historical authority retained by a queued action;
- changed authority version;
- narrowed authority;
- missing or unresolvable current authority;
- valid unchanged authority;
- first-time authority resolution after the last reversible boundary; and
- the exact frozen T0-T3 sequence.

## Post-fix result — SURVIVES

Tested repair head: `7be385362f5dd40e166ea00bb67cb86bcb067ef6` in PR #10.

GitHub Actions run: `34047633442`.

Results:

- Python 3.10: **success**
- Python 3.12: **success**
- Repository suite: **39 passed**
- Exact frozen T0-T3 adjudication: **SURVIVES**

The T3 execution trace is:

```json
{
  "authority_id": "frozen-authority-1",
  "queued_authority_version": 1,
  "queued_authority_status": "active",
  "queued_authority_scope": ["execute"],
  "current_authority_resolved": true,
  "current_authority_version": 2,
  "current_authority_status": "revoked",
  "current_authority_scope": ["execute"],
  "stale_snapshot_detected": true,
  "last_reversible_boundary": "DISPATCHED",
  "release_stage": "DISPATCHED",
  "final_decision": "block",
  "reason": "authority_revoked"
}
```

Interpretation: the queued action retains evidence that authority version 1 was active at T1, but that snapshot no longer governs T3. At release, the registry resolves authority version 2 as current, observes `revoked`, and blocks execution at the declared last reversible boundary.

## Evidence boundary

This result establishes only that the Syzygy Rosetta reference implementation survives this specific stale-authority falsifier and that the encoded regression cases pass in the repository test environment.

It does **not** establish real-world continuing governability, transport guarantees, distributed-state correctness, legitimate consent, correct identification of every real-world reversible boundary, revocation propagation across external systems, or effectiveness after an external irreversible consequence has already occurred.
