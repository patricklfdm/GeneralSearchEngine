# Original learner-to-voter resource handoff

The required-four native resource entry now binds the joining member's resource
journal to its independently derived placement and retirement originals.
Cancelling a learner does not exercise this path: joining retains the seed,
pending source, published INTENT, typed backup and dormant voter together until
the new native owner has a forced handoff decision.

## Admission and lifetime checks

`scripts.v53.native_resource_evidence` first requires the complete original
publication, physical, network, export and maintenance/ledger replay. For
`5-REPLACE-required-four`, `joined_handoff_resources` then derives the predecessor
reservations and native targets from the checked original files. Resource totals
and producer-authored `retirement.json` are not the expected-value oracle.

The new binding requires:

- The original joining node and all ten ordered custody, retirement, native
  handoff and opening callbacks, bound to its one complete resource journal.
- Every predecessor byte and distinct image reservation, including the full
  64 MiB typed-backup completion reservation. Equal image bytes in distinct
  owned files count separately.
- One atomic custody rename after the forced custody decision. The complete
  custody set remains continuously charged throughout placement, deletion,
  deletion-parent forces and the forced retirement completion record.
- One atomic replacement after the native decision is forced. Exact native
  journal, MISC, generation and image charges remain through native opening.
- No release/reacquire gaps hidden between callbacks, extra storage handoffs or
  outstanding reservations at the end of the original accounting journal.

The independently derived deletion list fixes every deletion ordinal and its
before/delete/force order. An omitted parent force or an omitted completion
record force is rejected even when the final surviving files look correct.

## Development verification

The retained original is
`general-search-engine-replication/target/v53-native-dispatch/run-bc82bb01-127a-40e0-9332-dd2f2bc8a1d3`,
from producer source `f0b60e1d1e93ff9c1e7a4ba2ced5e3b927fdc25f`.
It is the historical six-owner required-four original already referenced by
[basis resource binding](phase3-evidence/basis-resource-binding.json). The new
reader checks the entire byte inventory against that retained inventory before
qualification; no JVM workload is repeated or stitched into this history.

[The new development evidence index](phase3-evidence/joined-handoff-resources.json)
records complete original-first qualification in **438.95 seconds**, all 19
exact negative results and 132 related Python tests. All 535 earlier indexes
and the entire historical raw byte inventory are unchanged.

At the actual handoff this original has **11 predecessor leases**: two
GENERATION, one SOURCE, one LEARNER, one JOURNAL, one MISC and five APPLICATION.
It retains 9,007,296 metadata bytes and 67,201,089 staging bytes through all
**46 deletions / 138 deletion callbacks**, then atomically installs four native
leases with 35,695,017 metadata bytes and 837 staging bytes. These are actual
same-pool observations, not the sum of independent peaks.

The original-first negative entry is:

```bash
python3 -B -m scripts.v53.joined_handoff_negatives \
  general-search-engine-replication/target/v53-native-dispatch/run-bc82bb01-127a-40e0-9332-dd2f2bc8a1d3
```

It first admits the unchanged complete original, then requires all **19**
specific rejection reasons. Mutations change copied in-memory observations;
original files and identities remain fixed. Journal usage and checkpoint totals
are recomputed, so an unrelated stale hash or arithmetical inconsistency cannot
stand in for the intended lifetime rejection. Tests use explicitly synthetic
fixtures and grant no native execution credit.

## Remaining scope

This closes the accounting link across this actual joined-owner handoff. It does
not establish physical captures between every callback, OS-lock release order,
explicit joining-owner close intervals, process-death recovery, combined byte
maxima or final-source hosted qualification. The full journal closes at zero;
that does not invent an unobserved close call.

Predecessor amounts are compared as a multiset of category/byte extents, with
distinct continuous custody leases. This is not a per-file mapping to every
predecessor lease at every intermediate write. Native target names and amounts
are derived exactly from the surviving installed generation and original handoff.

The existing 566-history / 260-group catalogue is unchanged. Historical producer
bytes are development evidence only; the final-source resource execution and
all five [Phase 3 closure gaps](PHASE_3_QUALIFICATION_AUDIT.md) remain open.
