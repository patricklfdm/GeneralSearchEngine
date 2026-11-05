# Original floor-copy and local-pin resource lifetimes

The required-four resource reader now binds floor storage leases to the original
generation manifests and member bytes already admitted by the physical, network,
export, maintenance and continuous-ledger readers. Resource counters and writer
callbacks do not supply expected files or quorum authority.

For each complete floor, the reader derives the exact SOURCE metadata extent
(including `generation.gsr`) and each lexicographically ordered APPLICATION image
extent. Names bind to the original manifest digest and image ordinal. A direct
fixture floor reserves all copies before `FLOOR_RESERVED`; a network floor
reserves its first copy at that boundary and each further copy before creating
its directory. Existing copies stay charged through handoff and retirement.
All copy leases remain live through `FLOOR_RELEASE_CLEARED`, whose callback is
before resource closure, and close before `FLOOR_RELEASE_BEFORE_RETURN`.

Every original floor callback must have the exact expected copy extents. Every
copy reservation in the full mutation journal must belong to a derived floor.
The reader also checks each lease's continuous lifetime: releasing and reacquiring
an identical charge between two callbacks cannot pass merely because the callback
totals match. Extra temporary copies are retained in the journal and rejected as
unbound rather than hidden by zero usage at close.

Pinned local copies use the original selector's generation slot and image names.
Their generation/image reservations must cover the original bytes at every
resource mutation throughout the floor interval. Conservative larger existing
reservations are allowed within the independently enforced frozen limits. A copy
lease, another generation, a pending claim or a matching image of insufficient
size cannot replace the actual pinned generation's charge. The physical reader
separately requires the original selector/files to remain present and forbids a
duplicate local floor copy.

## Validation and scope

`scripts.v53.floor_resource_evidence` is integrated into the required-four native
resource entry. `scripts.v53.floor_resource_negatives` first admits the unchanged
complete native original, then mutates only in-memory resource journals and their
checkpoints. It preserves all original disk, wire, event and derived floor inputs.
Eleven coherent mutations check metadata/image sizes, copy identity/ordinal,
temporary copies, pin coverage and release/reacquire gaps. Recomputed totals ensure
an arithmetic mismatch cannot substitute for the intended lifetime rejection.

Fourteen conditional regression tests cover direct/network/pinned floors,
conservative pin reservations, repeated floors, complete event coverage and
original-first negative admission. Three additional future-ledger regressions
require a departing FINAL's nine original records, mandatory ACKs for voting
owners, and the existing strict original departure verifier.

The complete required-four native run at Java source `f0b60e1d` passed in 1334
seconds: all eleven slots, FINAL, the successor barrier and stable cold reopen.
All 1128 recorded Java/resource inputs remained unchanged during execution.
The first independent replay failed at node 3 / FINAL index 10 because the shared
future-ledger reader incorrectly required `applied-end/ack.gsr` on a departing
owner. The runtime intentionally omits that successor vote. The reader now admits
the existing nine-record proof only after strict departure verification; voting
owners still require the original ACK. No original bytes or Java were changed,
and the native experiment was not rerun to correct this reader.

Corrected complete replay of that same original passes physical/network/export/
maintenance and all four continuous ledgers, 81031 resource changes, 38783 event
checkpoints and 374 publication boundaries. Floor derivation binds 56 complete
floors, 358 copy leases, 6188 floor boundaries and three pinned originals checked
at 171 resource mutations. Connected transport derivation binds 19332 frame
lifetimes; 252 pre-connection allocations and 14148 other CONTROL reservations
remain explicit unqualified scopes. Accounting reservations are not claimed as
full simultaneous physical peaks. All 139 related Python/contract tests pass.
The fifteen original accounting mutations and eleven new floor mutations all
reject with their exact declared reasons. Complete repaired replay and these
negatives took 423.4 seconds; no workload measurement was repeated.

The [development index](phase3-evidence/floor-resource-binding.json) retains the
original inventory, first replay failure, corrected replay, negative outcomes and
source/report hashes. The larger existing ledger/export/maintenance negative
matrices and final-source hosted cohort remain separate execution obligations.

```bash
python3 -m unittest scripts.v53.test_floor_resource_evidence
python3 -m scripts.v53.floor_resource_negatives "$ORIGINAL"
```

This scope covers copied floor storage and the original pinned generation.
Receiving scratch handoff, other storage/control owners, full physical peaks,
capacity-bound completion histories, frozen coverage and final-source admission
remain separate obligations. Phase 3 remains open; twelve hosted subsets / 544
planned histories are unchanged. No Java, persisted/wire format, production limit,
workflow, Maven build parameter or paid-cloud behavior changes in this batch.

Rollback removes this reader, negative driver, tests and the required-four entry
call together. Original native bytes and their existing qualified scopes remain.
