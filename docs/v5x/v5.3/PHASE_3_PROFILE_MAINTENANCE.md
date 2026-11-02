# Phase 3 — profile maintenance authority

This composes [profile control exports](PHASE_3_PROFILE_CONTROLS.md) with the
original discovery, acquisition, floor, retirement and release history. The
previous ADD reader required a joining copy even where the governing old/new
majorities could both be satisfied by old voters. The retained ordinary
3-REPLACE history reproduces that mismatch. Runtime `MembershipFloor.create`
requires an exact local copy and both governing majorities; it does not add an
unconditional joining vote.

The profile adapter reuses the independent covering-floor derivation. Every
copy must retain its actual root, permanent identity, view, generation manifest,
members and exact covering ancestor. A larger index alone is insufficient.
The local generation must match exactly and a previous floor must be released.
For 3-ADD, the original old majority still cannot satisfy the new side without
the joining copy. The other declared joining profiles can have an old-only
joint majority; conditional tests check each profile separately.

Discovery binds the actual joiner (`node-4`, `node-5` or `node-6`) to its original
continuation endpoint and owner lifetime. STATUS remains a hint, with its exact
nonce, cut and correlation checked. Complete packets and generation metadata
must arrive before floor reservation. Borrowed application images must be the
actual original local bytes. Every observed floor transaction's full force
sequence, handoff, retirement interval and release deletion remains accounted for.
Every generation/source retirement callback must belong to that same owner's
reserved, unreleased floor. Deleting an entire floor transaction cannot leave
orphaned retirement callbacks that disappear from the surviving-floor count.

The fixture's direct copy calls are distinct from TCP acquisition. Their old
owners come from the original INTENT certificate's proof voters. Each must
complete exactly one direct floor using all those original live owners and the
actual joining owner. Every copy has an original callback and remains inside
the current generation and joining-owner lifetime. The adapter records the
original copy order for subsequent ledger composition. It does not invent a
network exchange for a direct fixture call.

The old fixture's fixed STATUS/floor totals are replaced by complete observed
event accounting and the exact direct-owner cohort. These totals were measured
fixture results, not frozen resource or timing limits. No protocol parameter,
workload, persistent format or Java implementation changes.

```bash
python3 -B -m scripts.v53.joining_profile_maintenance_evidence /path/to/original \
  --profile 5-REPLACE --qualify
```

The entire original physical/network/export/control chain must pass before
maintenance can qualify. Fifteen negatives mutate disposable event/wire copies
while preserving all original physical inputs. Each mutated transcript must pass
the preceding network, export and control gates before an exact maintenance
rejection counts. Missing targets, unrelated errors and accepted mutations fail.

The [receipt](phase3-evidence/profile-maintenance.json) records original
provenance, current reader hashes, negative results and extracted-archive replay.
The conditional joining-endpoint regression fails on the previous shared reader:
its hardcoded `node-4` comparison skipped the endpoint/lifetime check for actual
`node-5`/`node-6` joiners. The corrected reader rejects those mismatches. Conditional
tests remain separate from actual larger-profile native qualification.

An additional original-history negative removes the final network floor's
transaction callbacks while retaining its retirement callbacks, physical bytes
and wire transcript. The first adapter accepted this reduced history after the
network/export/control gates passed. The corrected adapter rejects it as an
unbound retirement event. Both reader versions and the disposable mutated history
are retained; the original was not modified. This closes the missing whole-floor
check when replacing the old fixture's fixed totals with observed accounting.

Measured validation: all 1,838 V5.3 Python tests pass, including sixteen new
conditional tests. The retained ordinary 3-REPLACE and historical 3-ADD each pass
fifteen exact maintenance negatives. REPLACE accounts for 34 network floors,
2 direct floors, 74 complete copies, 38 STATUS hints and 2,798 floor callbacks;
ADD accounts for 38 network floors, 2 direct floors, 96 complete copies, 55 hints
and 3,447 callbacks. All 1,942 REPLACE and 2,141 ADD retirement callbacks are
bound to their same-owner floor intervals. The existing full same-view composition
also passes.
These are three retained originals, not new larger-profile native executions.

All three results match after extraction and replay with Python assertions
disabled. The 45,795,601-byte archive retains 25,439
files, original producer metadata, both frozen reader attempts, the reproduced orphan-retirement mutation and
development diagnostics.
Original and extracted inventories remain unchanged.

## Remaining work and rollback

Continuous peer/learner/future ledgers, allocator/promise composition for larger
profiles, combined resource accounting, frozen S/N mapping and final-source
whole-history profile/process/fault cohorts remain OPEN. A qualified maintenance
floor does not establish those other layers. Phase 3 remains OPEN.

Rollback removes the profile adapter and reverts the shared actual-joiner checks,
preserving both the original evidence and failed-reader diagnostics. This batch
does not run native or paid-cloud experiments or change workflow execution.
