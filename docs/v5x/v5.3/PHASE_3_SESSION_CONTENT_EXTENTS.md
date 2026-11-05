# Phase 3 original successful-session content extents

This composes all ten successful export families with the original native
source-session bindings, following
[joining metadata extents](PHASE_3_JOINING_METADATA_EXTENTS.md),
[direct exports](PHASE_3_REQUIRED_FOUR_DIRECT_EXPORTS.md) and the
[published-prefix probe](PHASE_3_PUBLISHED_PREFIX_PROBE.md). Phase 3 remains OPEN.

## Independently derived charges

The complete required-four physical/network/control/maintenance precondition
runs first. The new reader uses its original content groups, generation windows,
forced sources, record capabilities and permanent identities to derive:

| Export | Binding | Exact CONTROL charge |
| --- | --- | --- |
| source | Original BASIS digest | Framed BASIS plus original PROMISE bytes |
| record | Original forced record digest | Framed record bytes |
| vote | Original payload digest or receipt alias | Original payload or receipt bytes |
| prefix | Original generation manifest digest | 4096 bytes |
| learner ROOT | Original ROOT record digest | Twice ROOT bytes plus 4096; separate nested 4096-byte prefix |
| joining retention | First request digest | 6 MiB; separate nested 4096-byte prefix |
| joining INTENT | First request digest | 65536 plus four times the six original framed records and decoded payload; separate nested prefix |
| joining preparation | First request digest | 32768 bytes |
| joining completion | First request digest | 32768 bytes |
| joining checkpoint | First request digest | Original pending CHECKPOINT_ACK bytes |

These are the existing production accounting rules. The reader does not derive
expected sizes or content identities from observed allocation labels or totals.
The existing joining metadata classifier supplies its already qualified formulas.

Original first-request bytes bind every successful session. Its node, logical
session identity, initial CHUNK shape, resource sequence and exact request digest
must match. Every owned export allocation must follow request reception, precede
session construction, match its independently derived role/binding/extent, and
remain covered by the existing cleanup reader. Nested prefix handles are checked
separately. Duplicate, missing or extra expected sessions fail; unrelated unowned
allocations keep the overall result PARTIAL.

## Entry

```bash
python3 -m scripts.v53.native_resource_evidence "$RAW" \
  --profile 5-REPLACE-required-four \
  --source-control --control-closes --export-ownership \
  --joining-requests --joining-extents --session-extents \
  --direct-exports --published-probe
```

`--session-extents` requires required-four, cleanup observations and export
ownership. It collects original initial requests even if the separate joining
request option is absent. The existing original source replay must finish before
any content-to-allocation binding runs. Direct operations, probes and constructor
rollback do not become successful sessions.

Reviewing the full producer also clarified the rollback boundary: its explicit
invalid INTENT and published-prefix constructor probes reject before allocating
their metadata/borrow. The INTENT capacity/expiry/fencing probes run only without
joint publication. The separate conditional rollback fixtures remain useful,
but no rollback interval is invented for these pre-allocation failures.

## Retained checks

- Seventeen new tests and adjacent suites total 324 passing Python tests. They
  cover all ten families, consistent-but-wrong resource totals, content aliases,
  nested generation/size, original routes and construction intervals, complete
  session coverage, unrelated unclaimed allocations and prerequisite ordering.
- Complete historical required-four admission and current-reader derivation
  pass in 209.617 seconds: 786 successful sessions require 792 handles. Counts
  are 263 record, 42 source, 240 prefix, 229 vote, one learner ROOT, two INTENT,
  three checkpoint, one preparation, three retention and two completion sessions.
- A separately recomputed direct-operation derivation contributes 72 handles.
  The historical node/role/extent census observes 865 allocations and leaves one
  node-1 prefix allocation of 4096 bytes after subtracting those two scopes.
  This is a census, not individual legacy-handle qualification or proof that the
  remaining allocation is the newly observed probe. The old capture lacks the
  current bindings; no observations are backfilled.
- Two retained actual conditional handler captures pass this new session reader
  and ten exact mutation checks, after their original component admission. Their
  outer scope remains PARTIAL. No Java workload was rerun in this batch.

Early synthetic fixture failures are retained: the old nested fixture put its
request boundary after the prefix reservation, and the first unclaimed-allocation
fixture omitted transition sequence metadata. Corrected fixtures preserve the
strict construction interval and complete journal rather than weakening checks.

The [development index](phase3-evidence/session-content-extents.json) records
source and report hashes. Local logs are under
`target/v53-session-content-extents/`. No production Java, POM, workflow, frozen
format, limit, deadline or paid-cloud change is included. Current-source full
resource execution, separate failure scopes, physical custody and simultaneous
maxima/headroom, cohort admission and final hosted qualification remain OPEN.
