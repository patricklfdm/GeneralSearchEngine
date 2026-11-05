# Phase 3 publication generation custody

This closes a specific gap in [publication storage boundaries](PHASE_3_PUBLICATION_RESOURCES.md):
an aggregate can balance even when the same bytes are charged to the wrong
generation or image. Phase 3 remains OPEN.

## Original authority and exact ownership

The complete independent physical/history replay and publication-inventory
comparison run first. Native resource replay then binds original permanent
identities, event sequences, journal arithmetic and closure. The new conditional
reader derives each generation's metadata extent and separately named image
extents from those admitted physical files. It does not use resource labels or
totals to choose the expected owner or size.

Both old and newly published slots retain their own identities, even when their
image bytes are identical. The reader also checks the existing fixed journal
and current-authority reservations, applied-end/replay completion reservations,
and all eleven publication boundaries. Every intervening resource mutation is
checked, including mutations absent from the physical callback list:

1. New generation metadata is reserved after publication validation and before
   `INSTALL_RESERVED`.
2. The existing 64 MiB publication-completion reservation transfers atomically
   to the new generation image in `EXTEND_COMMIT`. Releasing it and allocating
   another reservation is rejected even if callback totals are unchanged.
3. The image stays at its maximum reservation through current-directory force.
   One `GENERATION_RELOAD` then changes it to the admitted physical size before
   `PUBLICATION_SELECTOR_FORCED`. An actual maximum-sized image still requires
   this atomic boundary, although its byte delta is empty.
4. The applied-end and replay-input/output reservations release only after that
   boundary and before `PUBLICATION_RETIRED`. Old and new generation charges
   remain present through publication return.

This proves reservation custody for these publication intervals. It does not
claim Java handle identity across the supported atomic reload, physical custody
outside these intervals, every CONTROL/WAITER lifetime, simultaneous maxima,
or current-source final qualification.

## Integration and checks

`scripts.v53.native_resource_evidence` now always composes this reader after
its original admission; no new opt-in is necessary. Existing capture-layout and
export-ownership options still have to match the original producer. Independent
physical admission is required before the conditional reader or its negatives
can contribute to a native result.

Seventeen new tests cover valid handoffs, distinct equal-content slots,
same-total owner substitutions, metadata compensation, invisible custody gaps,
non-atomic transfer, early shrinking, maximum-sized no-delta reload, unrelated
CONTROL activity, original boundary binding and invalid-original rejection.
The adjacent Python suites pass 352 tests. The negative driver keeps ten
mutations legal and balanced under the accounting reader, then requires each
specific physical-binding rejection. It never rewrites retained captures.

The complete native composition passes against two unchanged historical captures:

| Original scope | Publications | Physical boundaries | Checked mutation states | Replay seconds | Exact negatives |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stable native TCP history | 4 | 44 | 34 | 3.283 | 10 |
| Required-four complete history | 34 | 374 | 272 | 312.729 | 10 |

The times describe local reader execution, not a new runtime measurement. All
twenty negative mutations still pass independent journal arithmetic and reject
for their exact declared ownership/custody reason. Historical producer evidence
is not relabeled as execution of the current runtime source.

The [development index](phase3-evidence/publication-generation-custody.json)
records retained original replay results and their hashes; local reports are in
`target/v53-publication-generation-custody/`. Initial stable replay invocations
omitted the capture's existing cleanup/export options and correctly failed
inventory/ownership admission. Those logs remain retained; the corrected
invocation uses the original capture's documented modes.

The qualification source inventory also includes the already implemented
session/direct/probe/rollback readers and tests from recent batches. The plan
still has twelve requirements and 544 planned hosted histories; its PASS is
source inventory only. No production Java, POM, workflow, frozen format, quota,
deadline, new runtime execution or paid-cloud change is included in this batch.
