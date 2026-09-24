# V5.1 Phase 6 entry: automatic leadership performance and cloud evidence

**Status:** entry and local contract accepted through [PR #215](https://github.com/patricklfdm/GeneralSearchEngine/pull/215),
master `243434f6e1dc94422b57997b33eabb3cc1e8f64d`, documentation-only master CI
`35831892351`. The [rich model foundation](PHASE_6_MODEL_FOUNDATION.md) is the first
6A implementation candidate. The [6A review](PHASE_6_LOCAL_ACCEPTANCE.md) now reconciles the full local gate through
PR #219; the [6B workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md) is accepted
through PR #222 with full master CI `35937300754`.
The [6C1 remote foundation](PHASE_6_REMOTE_FOUNDATION.md) starts remote implementation;
6C2 integrates the actual JVM workloads and 6C3 owns cloud orchestration/admission.
These review boundaries do not change the ordered 6C exit requirements or authorize
paid execution.

**Starting master:** `15c8c68011e37370dfcd31ee855f91247c3771d8`.
[PR #214](https://github.com/patricklfdm/GeneralSearchEngine/pull/214) accepted
[Phase 5](PHASE_5_ACCEPTANCE.md). Its [master CI 35830149418](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35830149418)
passed Change scope and Required, with full jobs correctly skipped for documentation.
The unchanged runtime was fully tested at `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`,
[CI 35826641489](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35826641489):
19 jobs, 23 V5.1 verification steps. The [Phase 5 ledger](PHASE_5_EVIDENCE_LEDGER.md)
retains the independently replayed public/internal evidence boundaries.

## Purpose and inherited boundaries

Measure the cost of automatic leadership, fresh-barrier strong reads and recovery
through the accepted public API. Establish source-bound concurrent three-voter
cloud evidence after local and remote qualification. Keep the accepted
[charter](../DEVELOPMENT_CHARTER.md), [automatic contract](PHASE_0_CONTRACT.md),
[resource/API rules](API_FORMAT_AND_COMPATIBILITY.md) and
[E01–E12 evidence contract](TESTING_AND_EVIDENCE.md).

Automatic reads add a replicated NO_OP without advancing application sequence.
Published V5.0 configured-leader reads and V4.4 local reads do not provide that same
quorum-backed guarantee. Report those modes separately; latency differences are
consistency/topology costs, not evidence that one version is a faster equivalent.
Automatic tests never manually activate a leader, suppress one voter's election for
convenience, expose follower application reads or re-enroll a missing voter disk.

## Existing assets and required additions

| Asset | Reuse boundary / work still required |
| --- | --- |
| [Public lifecycle consumer](../../../scripts/v51/java/PublicLifecycleConsumer.java) and Phase 4/5 harnesses | Public start/mutation/read/close, raw cut observations, owned crash/archive evidence. Add an external rich workload probe; the existing consumer's two-field documents are not the performance corpus. |
| [Published controls](published-controls.json) / [resolver](../../../scripts/v51/controls.py) | Exact V4.4 core and V5.0 core/replication hashes; independently compiled processes and loaded-code-source checks. Never substitute locally built V5.1 configured mode for published V5.0. |
| [V5.0 deterministic model](../../../scripts/v50/performance_model.py) | Reuse document/codec/query definitions as a compatibility reference. Its log model counts configured writes, not automatic read barriers; introduce a V5.1 model and leave historical plans untouched. |
| [Public history checker](../../../scripts/v51/public_history.py) | Bounded unique-addAll/match-all model for the small fault history. It does not support the rich ten-operation workload; that needs a separate decoded-prefix/query-cut oracle. |
| [Physical oracle](../../../scripts/v51/public_qualification_evidence.py) / [storage inspector](../../../scripts/v51/storage_inspector.py) | Preserve independent decoding, force/quorum/read-cut checks and all refusal classes. Extend explicitly for rich operations/measurement; a worker's summary is not proof. |
| [No-GCP planner](../../../scripts/v51/cloud_plan.py) | Existing `fake-control-plane-only` schema, topology/cost arithmetic and exact-ID cleanup model. It has no paid admission, real workload or remote runner. |
| [V5.0 runner](../v5.0/PHASE_6_CLOUD_RUNNER.md) / [remote qualification](../v5.0/PHASE_6_REMOTE_WORKLOAD.md) | Architectural reference for owned resources, preparation, retention and cleanup. New V5.1 suite, identities and validators must qualify separately; changing a suite string is insufficient. |

## Ordered delivery

| Batch | Deliverable | Required exit |
| --- | --- | --- |
| 6A — local measurement | Implement the [frozen local contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md), machine-readable plan, external candidate/control probes, bounded automatic failover history, independent measurement/semantic validators and one bounded CI gate | Complete local preset, resealed evidence negatives, existing public/compatibility gates and exact-source full CI. Record actual cost of instrumentation and actual gate duration. No GCP. |
| 6B — cloud workload freeze | Calibrate proposed scale locally; review complete experiment/failure/canonical workloads, rate/window/count/byte arithmetic and acceptance criteria in a separate cloud plan | Exact corpus, seed, mix, arrivals, concurrent callers, fault order, repetitions, all sub-budgets and immutable plan hashes accepted before paid preparation. Local calibration is retained and labelled; it is not canonical evidence. |
| 6C — runner and remote qualification | V5.1-owned prepare/run/collect/validate/cleanup path, fake adapter exercising those same decisions, separate source-bound admission and workflow identities | Full-size serialization/resource checks, local remote-adapter execution, interrupted provisioning/SSH/upload/cancellation/deletion negatives, full CI and reviewed cloud configuration. No paid run inferred from merge. |
| 6D — manually triggered cloud sequence | Fresh read-only preflight, current-price estimate, exact request confirmation; one experiment, one failure-drill and three canonical repetitions | Every member validates independently; evidence retention and exact resource absence verified before another member. All five share admitted source/artifact/workload identities. |
| 6E — review and registration | Reconcile raw member/set results, costs, failed attempts and cleanup; append-only baseline registration through a separate PR | Complete accepted set, retrievable raw evidence and exact measured source. Only then enter Phase 7. |

6A may be delivered as a substantial implementation batch, splitting only where a
concrete review boundary requires it. The first such boundary is the
[rich model and published-control foundation](PHASE_6_MODEL_FOUNDATION.md): the old
public history checker cannot validate this ten-operation rich program. Review its
independent decoder/control parity before accepting measured automatic traces. Integrate its CI gate once with always-retained
evidence; use observed job timings to place it without serializing the existing
lanes. Do not rerun unchanged large matrices merely to fill a documentation PR.
A code/plan/build-input change requires the relevant full checks before new admission.

## Cloud coverage to freeze in 6B

The following selects required cloud behaviors; it does not claim every E row will
be re-executed in paid infrastructure. Their accepted deterministic/internal tests
remain regression prerequisites. Exact durations, loads and byte limits are 6B outputs.

| Cell family | Required observation | E mapping |
| --- | --- | --- |
| Healthy automatic / read-heavy / concurrent sustained | Paired semantics, per-operation outcomes, fresh read barriers, instrumented versus baseline overhead, bounded queues and retained ancestry | E01, E09, E10, E11 |
| Leader SIGKILL and retained rejoin | Surviving majority elects/activates without operator promotion; first durable write/strong read; old retained voter rejoins without restoring a copied authority | E01, E05, E08, E10 |
| Isolated old leader, including asymmetric traffic | Minority refuses new reads/writes; majority advances; delayed old messages do not restore old service; heal/rejoin | E02, E03, E06, E09 |
| Slow follower / lagging voter recovery | Remaining quorum progress, measured lag/bytes, bounded transport, verified snapshot/basis transfer including interruption | E07, E11 |
| Entry-chosen and proof-quorum crash cuts | Distinct uncertain responses, preserved chosen value and acknowledged prefix through a new leader; no fabricated client success | E04, E05, E06 |
| Whole retained group restart | New process identities and durable authority retain acknowledged state and exclusive ownership | E01, E08 |
| Pinned read, checkpoint/backup and close | Read remains on its captured cut; bounded pins/retention; completed V4-compatible backup survives and independently restores | E07, E09, E10 |
| No quorum, then heal | Fresh automatic reads and writes fail conservatively; status does not stand in for a successful query; eventual measured recovery under restored conditions | E03, E10, E11 |
| Minority resource refusal | Actual bounded rejection preserves valid sources and healthy majority service; no invented reclaimed capacity | E10, E11 |

Same-group disk replacement is excluded in automatic mode. If 6B elects to include
physical disk loss, it must freeze quarantine and a separately identified **new-group**
verified-cut import, with new group/disk/resource identities; a saved diagnostic copy
cannot secretly serve as the lost disk. V5.0's same-group replacement cells cannot be
copied here. Wrong-mode/format/API rejection (E12) remains an exact-source local gate.

## Planning ceilings and paid boundary

The following are proposed V5.1 planning ceilings, consistent with the existing fake
planner; they are not a fresh quota, image, price, budget reservation or paid approval.

| Item | Ceiling / required decision |
| --- | --- |
| Simultaneous resources | Three voter VMs, 8 vCPU each; three 50-GiB boot plus three 100-GiB data disks: 24 vCPU / 450 GiB peak. Controls run sequentially on these hosts. |
| Provider selection | Historical reference: Standard `n2-standard-8`, `us-west4-a`, `pd-balanced`, ext4. 6B/6C must resolve and freeze exact supported image/JDK/SKU/network/volume inputs; no floating image or old availability receipt. |
| Topology lease | At most 5400 seconds plus at most 1080 seconds operation grace. The 6B allocation must include startup, both controls, candidate warmup/cells, control overhead, validation/retention and cleanup; cleanup has an explicit reserve of at least 300 seconds. |
| Aggregate budget proposal | USD 100 for the new V5.1 sequence, including controls, failed attempts, storage, transfer, retention and cleanup. User confirms a fresh priced request; the V5.0 ledger is not reset, transferred or reused. |
| Baseline set | One experiment + one failure-drill + three serial fresh canonical topologies. No simultaneous topologies or extra control VMs. |
| Evidence | 6B freezes maximum expanded/compressed bytes, members, parts, diagnostics, retention duration and total storage cost before implementation admits them. |

For five members at the full lease plus grace, planning reserves 27 VM-hours and
4050 GiB-hours of disks before evidence/transfer charges: `5 * 3 * 6480 / 3600`
and `5 * 450 * 6480 / 3600`. These are cost units, not prices or a guarantee that
an unavailable provider will delete resources within grace. Unresolved cleanup is
a failed run and blocks further allocation; actual overhang remains chargeable.
If fresh pricing cannot fit the complete sequence and retry reserve, review scope
or budget before resource creation. The fake planner's USD 5 per-run input is not
a priced estimate and must not be presented as one.

Preserve the existing operator choices while making them source/suite specific:

- Separate V5.1 workflow/ref/environment/WIF allowlists, no automatic paid dispatch
  from push, PR or schedule. User controls actual cloud triggering.
- Preparation emits an exact request digest and fresh expiring preflight. Proposed
  maximum receipt age is 900 seconds, checked at admission; expiry after an admitted
  start does not retroactively abort a valid measured run. Runtime lease is separate.
- Require a successful, actually executed **scheduled or safe manual cleanup** for
  the exact accepted source within two hours. Both reconcile retained leases using
  the same implementation; manual changes timing only, never expiry/grace/ID rules.
  Environment approval alone is not a cleanup receipt.
- Renew credentials during long runs and retention; bind partial uploads and remote
  commands to exact attempt IDs. A dropped SSH response is not permission to replay
  a possibly accepted mutation. Inspect/poll a durable command receipt or fail and
  retain evidence; test this before paid execution.
- Evidence-retention failure must not suppress cleanup. Confirm absence by exact
  resource identity/read-back and preserve leftovers; cleanup cannot delete accepted
  evidence, an active lease or unrelated resources.

The first member locks either experiment → failure-drill → canonical 1/2/3, or
canonical 1/2/3 → experiment → failure-drill, honoring the existing canonical-first
operator preference. Either order requires accepted local/remote qualification and
all five passing members. Failed attempts remain in an append-only budget/history;
no automatic refund or rollback. An approved retry has a new attempt ID and remaining-budget admission. A failed
canonical member requires a fresh comparable set/sequence; it cannot be selectively
replaced inside a successful set.

## Measurement and acceptance rules

The [local contract](PHASE_6_LOCAL_MEASUREMENT_PLAN.md) defines clocks, outcomes,
semantic oracles and negative fixtures reused by later measurements. Cloud fixed-rate
windows additionally retain scheduled/actual arrivals and unfinished calls. No hidden
queue, burst catch-up, read resampling or erased refusal may rescue a missed preset.

There is **no pre-existing throughput improvement or p99 SLA** to mark as passed.
6B must freeze offered-load completion/availability criteria, fault recovery ceilings,
resource/evidence limits, instrumentation overhead acceptance and all numerical
thresholds before canonical execution. Freeze control/candidate placement and mode order too;
record actual leader/host identities and compare on matched host classes, without
forcing automatic election winners to make timings look comparable. Relative mode comparisons are descriptive
unless an explicit reviewed target is added. Report each repetition and sample count;
small fault histories cannot support general p99 claims. Failed seeds/members stay visible.

6B is BLOCKED for paid use until that closed plan exists. 6C is BLOCKED for paid use
until its implementation, fake/remote evidence and fresh admission pass. This entry
plan does not silently promote the current fake planner or reduced local smoke.

## Documentation validation and handoff

Validate source/acceptance references, local workload/corpus/count/resource arithmetic,
all new/changed Markdown links/anchors/fences, contract gates, CI-classifier tests and
preservation of published controls/charter/production/workflows. All changes in this
batch are Markdown, retaining the standard docs-only CI path.

After protected entry acceptance, 6A started with the
[local measurement plan](PHASE_6_LOCAL_MEASUREMENT_PLAN.md) and
[Phase 6 checklist](PHASE_6_CHECKLIST.md). Commit, push, PR and merge remain user-owned.

## Validation of the accepted entry

- Independent static calculation reproduced the 64-document corpus digest, 3149
  encoded corpus bytes, all 90 calls/72 mutations/18 reads, final application sequence
  76 and peak 68 documents. Generated documents/payloads peak at 58/285 bytes.
- Local stage reservations sum to 900 seconds. Healthy/fault logical-slot bounds
  are 162/90 below 192; the small history is at most 18 calls. Full five-member
  lease-plus-grace cost units are 27 VM-hours and 4050 GiB-hours of disks.
- Existing foundation gate passed version/contract checks, 267 V5.1 Python tests
  and independent model/format evidence. This is prior-runtime/foundation validation,
  not execution of the proposed performance preset.
- All 19 CI classifier/topology/Required tests passed. Changed/new Markdown links,
  anchors, fences and whitespace passed; all fifteen paths classify as docs-only.
- No production code, test implementation, workflow, published artifact pin, accepted
  V5.0 contract or executable cloud plan changed.

Local calculation/check logs: `target/v51-phase6-entry/validation.json`,
`validate_plan.py`, `foundation.log`, `ci-tests.log`. Foundation evidence:
`target/v51-foundation/run.Agw5VR/evidence`. Actual performance and cloud results
remain unchecked in the Phase 6 checklist.
