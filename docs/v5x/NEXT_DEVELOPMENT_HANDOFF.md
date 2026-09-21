# Next-development documentation handoff

**Status:** local documentation integration and review record, 2026-09-19.
The V5.1-V5.4 refinements and V6 preview remain PROPOSED. Integration does not
constitute protected acceptance of a protocol or authorization to implement it.

**Reviewed source:** `066a04602f7116a0386c645ddfcf4c2e3d41312a`.

**Subsequent design handoff:** after planning PR #183, the user started V5.1 Phase 0
on source `09d2bf247f004eb134eb81c59ee88005affafe92`. The
[contract candidate](v5.1/PHASE_0_CONTRACT.md) now supplies all six design outputs;
its [checklist](v5.1/PHASE_0_CHECKLIST.md) records current review/acceptance state.
The integration record below retains the original boundary and validation history.

**Current implementation handoff:** V5.1 Phase 4D was accepted through PR #195 at
`da9f3e9fe957e61c0fe45cf041431a5c4c74cd79` (exact-master CI `35570118695`).
[Phase 4E recovery/lifecycle](v5.1/PHASE_4_PUBLIC_RECOVERY.md) adds imported failover,
rejected authority, cancellation/close and cursor reconstruction evidence. Follow the [current Phase 4 checklist](v5.1/PHASE_4_CHECKLIST.md)
and its remaining public scenario mapping; this does not authorize Phase 5, cloud
runs or publication. The original Phase 0 planning-only restrictions below describe
that earlier task.

## Self-contained development map

The revision 0.1 proposal's development material is integrated at the following
canonical destinations. This handoff retains the useful import, provenance and
review guidance; future development uses these repository documents directly.

| Material | Destination |
| --- | --- |
| Current development entry and historical navigation | [Root roadmap](../../DEVELOPMENT_ROADMAP.md) |
| Complete document navigation | [Documentation index](../README.md) |
| V5 overview and preserved authority map | [V5 README](README.md) |
| Version sequence, references and proposed acceptance boundaries | [V5 roadmap](ROADMAP.md) |
| Cross-version scope, compatibility, reads, operations and evidence rules | [Next-development addendum](NEXT_DEVELOPMENT_ADDENDUM.md) |
| V5.1 design task, D01-D12, E01-E12 and six planned deliverables | [Phase 0 entry plan](v5.1/PHASE_0_ENTRY_PLAN.md) |
| Research status and provisional V6 release labels | [V6 overview](../v6x/README.md) |
| Partitioning, remote queries, atomicity, views, relocation and scaling | [V6 architecture preview](../v6x/ARCHITECTURE_PREVIEW.md) |

The original patch, duplicate document copies, import commands, checksum list and
packaging reports are delivery material, not additional development contracts.
They are not prerequisites for using this map. Do not reapply the original patch
over these already integrated documents.

## Start the next design assignment

1. Inspect applicable repository/ancestor agent instructions, `git status --short`
   and `git rev-parse HEAD`. Reconcile changes since the reviewed source. Preserve
   unfinished user work; do not silently stash, reset, overwrite or switch branches.
2. Read the root roadmap, documentation index, [accepted charter](DEVELOPMENT_CHARTER.md)
   and V5 roadmap above. Published guarantees and accepted version-specific contracts
   govern; a newer proposal does not supersede them by its filename or date.
3. Read the V5.0 [public-admission contract](v5.0/PUBLIC_ADMISSION_CONTRACT.md),
   [runtime record](v5.0/PUBLIC_ADMISSION_RUNTIME.md),
   [API delta](v5.0/PUBLIC_ADMISSION_API.md),
   [public 1.1 format](v5.0/PUBLIC_ADMISSION_FORMAT_1_1.md),
   [recovery/failure contract](v5.0/PROTOCOL_RECOVERY_AND_FAILURES.md) and
   [release reconciliation](v5.0/RELEASE_CHECKLIST.md). Distinguish historical internal
   1.0 fixtures from the admitted public 1.1 authority and later acceptance records.
4. Review the current implementation surfaces listed by the V5.1 entry plan and
   the existing [documentation gate](../../scripts/verify-v50-phase0-contract.sh),
   [change classifier](../../scripts/ci_changes.py) and [CI workflow](../../.github/workflows/ci.yml).
5. Once the user explicitly starts V5.1 Phase 0, use its entry plan as the design
   specification. Produce the six documents named in its
   [deliverables section](v5.1/PHASE_0_ENTRY_PLAN.md#7-concrete-phase-0-deliverables),
   resolving decisions through source inspection, counterexamples and review.
   That assignment still stops before separately authorized Phase 1 work.

At the original integration boundary D01-D12 were OPEN, E01-E12 were planned evidence
families, and the six Phase 0 output documents had not been produced. Do not invent
protocol proof, API compatibility, numerical defaults or acceptance evidence to
close them. A planning-document merge does not establish a completed Phase 0.

## Review boundaries to retain

Every later design review must preserve these distinctions:

- Published V5.0 guarantees, future V5.1-V5.4 scope and unapproved V6 research.
- V4.4 search/storage truth and V5.0 immediate replication compatibility.
- V5.1 leader-read safety and later public follower reads.
- Compatible configured-leader use and the proposed opt-in automatic mode.
- Indeterminate mutations and proven, safely retryable pre-dispatch rejections.
- Learner catch-up and safe voting-configuration transitions, including the existing
  V5.0 same-NodeId replacement boundary.
- Same-version rolling restart and mixed-version rolling upgrade.
- Per-shard atomic operations and a batch spanning multiple shards.
- A local Java Query lambda and a supported remote query AST.
- A vector of pinned shard views and a globally simultaneous snapshot.
- Fixed-load correctness evidence and measured physical scaling.
- Adopting an entry plan, accepting a full protocol and authorizing implementation.

Keep the accepted charter, V5.0 documents, release hashes and registered evidence
unchanged during this planning work. Preserve historical acceptance sections in
the root roadmap and V5 navigation. Historical corrections require an explicitly
identified erratum; they must not conceal an incompatibility in a later proposal.

The integration and documentation-only Phase 0 scopes do not include
production or test code, declaration classes, fixtures, version/dependency changes,
workflow changes, cluster startup, fault execution, paid cloud runs or publication.
Commit, push and merge remain user-owned operations. V6 research may proceed as
separately assigned design work; its proposed production gate remains a mature
V5.4 handoff unless explicitly revised through review.

## Provenance and integration review

The original proposal was revision 0.1 dated 2026-09-19, based on the reviewed
source above. All four original Git blob identities matched the actual checkout:

| Original file | Base Git blob |
| --- | --- |
| V5 README | `04b3218e31121bc2faf9b209da5043310703da07` |
| V5 roadmap | `926bf1551f7e67b161da7853b0eccc87c9f55165` |
| Root development roadmap | `d5fb7c56db5cc7893f4688476d088c341d4a13c1` |
| Documentation index | `272ff7a17617f7e37a508123064ef3c9420ac17f` |

Original patch SHA-256:
`e76de7161a2336bfdac2c11debf59ba1f34632ffb5acb2ad86156dcd3607fd9d`.
This identifies the imported patch, not a release artifact or the subsequently
clarified working tree. The full package checksum list passed before removal.

The package author had reviewed complete V5 README/roadmap content but only prefixes
of the two larger indexes. Its 119-reference check and patch application used
retrieved fixtures; it did not run the actual repository gate. Local integration
subsequently checked the real base blobs, ran `git apply --check` successfully and
applied all four modifications plus four additions without conflict. The package
was not copied on top of the applied patch.

Review added three clarifications: integration versus a separately assigned design
task, pre-dispatch rejection versus indeterminate mutation, and fixed-identity disk
replacement versus membership change. This handoff then consolidates the remaining
development guidance, bringing the proposed repository change to nine Markdown files.

The published V5.0 commit remains `e6afb5349c018fe163d4938d7637a4de8854d4ea`;
its measured cloud source remains `340df06148bc7d5a25a29a55c3ee928c9472dd09`.
Neither is relabelled as this documentation review source.

## Validation and reporting

Run the existing lightweight checks from the repository root:

```bash
git diff --check
scripts/verify-v50-phase0-contract.sh
python3 -m unittest scripts.test_ci_changes
git status --short
```

Also check every added or changed Markdown document, including `docs/v6x/`, for
local targets, anchors, balanced fences, trailing whitespace, final newlines,
proposal status, source identities and path containment. Include untracked files;
`git diff` alone omits them. Verify the accepted charter and V5.0 files against the
reviewed source and compare the preserved historical sections byte for byte.
The existing V5 gate covers a limited required-file list, so it does not replace
the expanded document walk. Let the existing classifier decide CI scope.

Local integration passed whitespace, the V5 contract gate, all 14 classifier tests,
the expanded document checks and preservation of all 60 protected charter/V5.0
files. No Java, runtime, consensus, cloud or publication validation was rerun for
this documentation task. The external etcd/Elastic references retained in the
design documents are comparisons, not evidence of GSE protocol correctness.

Report the exact reviewed source, local changes, commands/results, actual conflicts,
incomplete checks and unresolved design decisions. Record protected-review and
exact-master CI acceptance only after they occur. Stop at the assigned phase boundary.
