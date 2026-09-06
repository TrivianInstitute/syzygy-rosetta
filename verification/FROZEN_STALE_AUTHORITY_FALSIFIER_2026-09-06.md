# Frozen Stale-Authority Falsifier — 2026-09-06

## Status

This record preserves the distinction between the pre-fix failure and the post-fix result. The frozen test sequence and adjudication are not changed by the repair.

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

This failure is preserved by the regression witness `test_prefx_failure_witness_historical_snapshot_remains_locally_valid`. That test demonstrates the historical defect but is not an approved queued-execution path.

## Minimal repair

The candidate repair remains standalone inside Syzygy Rosetta and uses only the Python standard library:

1. `AuthorityGrant` gains an immutable monotonically increasing `version`.
2. Renewal, narrowing, revocation, and invalidation create a new authority version.
3. `AuthorityRegistry` holds the canonical current grant for each `authority_id`.
4. Queued work captures a `QueuedAuthorityReference` containing historical provenance, not continuing authority.
5. `validate_queued_authority()` must resolve the current grant from the registry before release.
6. Missing current authority, version regression, revoked/invalidated authority, expired authority, changed state, or current out-of-scope authority fail closed.
7. A changed but still-valid authority version may permit execution only after current re-resolution; the historical queued snapshot never authorizes by itself.

## Required regression cases

The test surface distinguishes:

- current revoked authority;
- stale historical authority retained by a queued action;
- changed authority version;
- narrowed authority;
- missing or unresolvable current authority;
- valid unchanged authority; and
- the exact frozen T0-T3 sequence.

## Post-fix result

**Pending CI on the repair branch.**

This section must be updated only after the exact frozen sequence and the full repository test suite have run successfully.

Passing the frozen test will establish only that the Syzygy Rosetta reference implementation survives this stale-authority falsifier. It will not establish real-world continuing governability, transport guarantees, distributed-state correctness, legitimate consent, or effectiveness across external irreversible systems.
