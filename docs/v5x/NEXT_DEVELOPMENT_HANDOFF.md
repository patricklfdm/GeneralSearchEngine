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

**Current implementation handoff:** full V5.1 Phase 4 is accepted through PR #208 at
`b0d586f32b01f59aadfa940d7f778a8a2b5ea078` (exact-master CI `35802660895`, all 13 jobs passed).
The [final Phase 4 review](v5.1/PHASE_4_FINAL_COVERAGE.md) preserves the E01–E12
public/internal evidence boundaries. [Phase 5A combined recovery](v5.1/PHASE_5_COMBINED_RECOVERY.md)
is accepted at master `04d12316bd6971ac477cfcb08c5073b2252ecf2a` (exact-master CI
`35818964327`, all 19 jobs passed). [Phase 5B combined lifecycle](v5.1/PHASE_5_COMBINED_LIFECYCLE.md)
is accepted through PR #213 at `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`, exact-master
CI `35826641489` (all 19 jobs and 23 V5.1 verification steps passed).
[Full Phase 5](v5.1/PHASE_5_ACCEPTANCE.md) is accepted through PR #214 at
`15c8c68011e37370dfcd31ee855f91247c3771d8`, docs-only master CI `35830149418`.
Its review retains the 23 public/eight internal cases on the unchanged fully tested runtime.
The [Phase 6 entry](v5.1/PHASE_6_ENTRY_PLAN.md) and
[local measurement contract](v5.1/PHASE_6_LOCAL_MEASUREMENT_PLAN.md) are accepted through
PR #215, master `243434f6e1dc94422b57997b33eabb3cc1e8f64d`, docs CI `35831892351`.
The current [rich model foundation](v5.1/PHASE_6_MODEL_FOUNDATION.md) implements the
closed local plan, independent rich prefix decoder and actual published V4.4 parity.
It is accepted through PR #216, master `bcac615aeef93dadcab6636162a86ce2156e5515`, exact-master full CI `35841378072`.
The [local runtime candidate](v5.1/PHASE_6_LOCAL_PERFORMANCE.md) adds the three-mode
measurement gate and bounded automatic SIGKILL/rejoin history. PR #217 merged at
`e3efda820beef9efcd6f6f06e8af71006c3b85ce`, exact-master full CI `35889987294`
(all nineteen jobs passed). The separately retained local resource-recovery failure
has a [scheduling correction candidate](v5.1/PHASE_4_RESOURCE_LIMITS.md#recovery-scheduling-after-the-phase-6a-resource-rerun).
PR #218 merged that correction at `84990b3fa6d5007b90427c95f376473c8db48bd9`.
Its PR CI `35894824934` passed; master CI `35896844608` failed the earlier public
bounds gate on a [single-permit driver race](v5.1/PHASE_4_PUBLIC_BOUNDS.md#post-pr-218-correction-observe-released-admission),
so the resource step was skipped. PR #219 then passed exact-master CI `35920225478`
at `54e203eeca6c087b7ba03954d546c7682e8338f2`, all nineteen jobs and 24 V5.1 steps.
The [6A review](v5.1/PHASE_6_LOCAL_ACCEPTANCE.md) independently replays that raw
performance evidence and corrects portable evidence inspection without changing
live authority admission. The [6B cloud contract](v5.1/PHASE_6_CLOUD_WORKLOAD_CONTRACT.md)
is a closed candidate with local calibration, synthetic full-slot encoding and
fifteen canonical cells. PR #220 merged at `717bed8f578019c71ffe3d739deaf067ec0fa8d2`;
master CI `35927462738` failed an inherited
[Phase 5A recovery-write assumption](v5.1/PHASE_5_COMBINED_RECOVERY.md#post-pr-220-correction-a-recovered-read-does-not-lease-leadership).
PR #221 merged that correction at `af68d8473f9998628e49189a2d8be658b8bfe116`.
Master CI `35932225694` exposed a separate
[proof-sample boundary and inherited retry fixture](v5.1/PHASE_5_COMBINED_RECOVERY.md#post-pr-221-correction-confirm-proof-before-recording-a-drained-round).
PR #222 accepted both corrections at `33aa89bf8a6b4b0587fa6a127e481d73671a60ec`;
exact-master CI `35937300754` passed all nineteen jobs and 24 V5.1 verification steps.
6A/6B are accepted under the [checklist](v5.1/PHASE_6_CHECKLIST.md).
The [6C1 remote control foundation](v5.1/PHASE_6_REMOTE_FOUNDATION.md) now implements
persistent command claims, fixed arrivals, time accounting and binary collection,
with control-only local qualification. PR #223 accepted it at
`833da4947266b4edfbee2a0e6fe10055ed3be00c`, exact-master CI `35942555519`
(nineteen jobs and 25 V5.1 verification steps passed). PR #224 accepted
[6C2A rich workloads](v5.1/PHASE_6_REMOTE_RICH.md), exact-master CI `35961961431`
(twenty jobs, 26 V5.1 gates). PR #225 accepted the
[6C2B fault workloads](v5.1/PHASE_6_REMOTE_FAULTS.md) and the two approved document-size
exceptions: master `22328ed4dc358e0adc7fde1399528295ebf8d2a3`, exact-master CI
`35989431966` (all 21 jobs). PR #227 closed [rich CI sharding](../CI_V51_RICH_SHARDS.md)
on master `2db90846606547325c2f35a466813c622cc1ffac`, CI `36064320654` (all 26 jobs).
The [512-slot component gate](v5.1/PHASE_6_FULL_SIZE.md) was accepted through
PR #228 at `3c3d9d19c8aa1d24aa88f971c983235bd186033d`, exact-master CI `36072038218`.
The [public runtime integration](v5.1/PHASE_6_FULL_SIZE_RUNTIME.md) was accepted
through PR #229 at `57622552e02addfae991642786e1a87a0633fb43`, exact-master CI
`36094121631` (all 27 jobs), closing full-size 6C2 under unchanged deadlines.
[6C3A cloud control](v5.1/PHASE_6_CLOUD_CONTROL.md) is accepted through PR #230,
master `2db3ebb645907eaa8b02fa849302c35accb03ff4`, exact-master CI `36105310891`.
Its first PR attempt's Maven transport and burst timing failures remain recorded;
the successful rerun does not establish a timing root cause. The [6C3B guest/provider gate](v5.1/PHASE_6_CLOUD_PROVIDER.md) is accepted through
PR #231, master `5b101a6e73a83ef9091ea369997f4d01e6ca4c26`, CI `36113872308`.
The [6C3C1 guest slice](v5.1/PHASE_6_GUEST_SERVICE.md) is accepted through PR #232,
master `2183dafa618238f0b824fc0a3b3d42624ce24782`, exact-master CI `36124423253`
(all 27 jobs). Its initial rich timing failure remains recorded; the rerun does not
establish a timing cause. The [6C3C2 bootstrap slice](v5.1/PHASE_6_GUEST_BOOTSTRAP.md)
is accepted through PR #233, master `d27da43086406384ab41cab6704541015aa0a1bf`,
CI `36149275698` (27 jobs). The [6C3C3 owned startup slice](v5.1/PHASE_6_GUEST_STARTUP.md)
is accepted through PR #234, master `79344fca6b447a3e77205be36d3d16e597d4bc23`,
exact-master CI `36185893530`, attempt 2 (all 27 jobs). Its first concurrent
measurement's 63.021587 ms burst spread remains a retained failure; no timing
cause is established by the successful rerun.
The [6C3C4 helper delivery candidate](v5.1/PHASE_6_GUEST_DELIVERY.md) adds a closed,
digest-authenticated helper payload, consumed installation claims and real
loopback OpenSSH receipt-query qualification. Native cloud SSH, cross-host
deadline translation, root admission and disk writes remain closed. Next connect
privileged delivery and volume readiness to packaged services under the owned
controller, finish remote faults/oracles, then trusted preflight and separate
workflows/configuration. Paid experiments remain user-triggered after exact-request confirmation.
The original Phase 0 planning-only restrictions below describe that earlier task.

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
