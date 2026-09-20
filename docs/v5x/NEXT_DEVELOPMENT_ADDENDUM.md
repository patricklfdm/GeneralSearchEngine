# V5.x next-development addendum

**Status:** PROPOSED, revision 0.1, 2026-09-19. Not an accepted contract or implementation authorization.

**Review base:** `066a04602f7116a0386c645ddfcf4c2e3d41312a`.

**Governing document:** [Accepted V5 development charter](DEVELOPMENT_CHARTER.md).

## 1. Purpose and authority

Retain the accepted V5.1, V5.2, V5.3 and V5.4 sequence. This proposal makes the
next entry point and cross-version obligations explicit; it does not replace the
accepted charter, rewrite V5.0 evidence, or claim that a V5.1 protocol is proven.

The next engineering task identified here is the documentation-only
[V5.1 Phase 0 entry plan](v5.1/PHASE_0_ENTRY_PLAN.md). It has since been assigned;
the [contract candidate](v5.1/PHASE_0_CONTRACT.md) and
[review checklist](v5.1/PHASE_0_CHECKLIST.md) record its proposed resolutions.
V6 is an
[architecture preview](../v6x/ARCHITECTURE_PREVIEW.md), not an implementation lane.
Acceptance of a planning document is distinct from acceptance of a complete minor
contract, authorization of the next phase, execution of paid work, and publication.
Record each actual decision separately. Do not mark a checklist passed merely
because this proposal has been copied or merged.

On a conflict, published guarantees and accepted version-specific contracts take
precedence over these proposed refinements. A conflict must be resolved explicitly,
not by applying a generic 'newest file wins' rule.

## 2. Preserve the completed foundation

The [V5.0 release record](v5.0/RELEASE_CHECKLIST.md) identifies published commit
`e6afb5349c018fe163d4938d7637a4de8854d4ea`. The
[cloud baseline](v5.0/PHASE_6_BASELINE.md) identifies measured source
`340df06148bc7d5a25a29a55c3ee928c9472dd09`. The review base is a subsequent
publication-documentation commit. These identities must remain separate.

Published `4.4.0` remains the search/storage truth and failure-classification
reference. Published `5.0.0` becomes the immediate replication compatibility
reference for V5.1. Each subsequent minor also pins its immediate published
predecessor rather than dropping earlier guarantees.

Do not edit V5.0 protocol bytes, accepted checklists, registered evidence, canonical
hash inventories or release identities to make later work appear compatible.
Necessary corrections to historical records require a separately identified erratum.
Patch releases may fix defects within the published boundary, but must not introduce
automated elections, follower reads or membership changes as unreviewed patch work.

## 3. Proposed scope ownership

| Version | Required result | Specifically not implied |
| --- | --- | --- |
| V5.1 | Safe automated leadership and rejoin in a fixed three-voter group; complete public write and leader-read admission | Follower reads, dynamic membership, transparent mutation retries, arbitrary mixed-version operation |
| V5.2 | Explicit replica-read policies and history-bound minimum-progress tokens | A stale read being latest, a minimum-index read being globally freshest, linear read scaling |
| V5.3 | Controlled membership transitions, node replacement and maintenance | A caught-up learner alone proving safe reconfiguration; rolling restart proving rolling upgrade |
| V5.4 | Combined-fault, sustained-operation and resource closure; stable group handoff | Universal availability, unlimited corpus size, untested cross-region guarantees |

Each minor has its own accepted Phase 0 before production implementation. Later
phase plans may be refined using observed evidence, but may not weaken published
safety to meet an attractive throughput number or an artificial version deadline.

### V5.1: automatic leadership, not a heartbeat-only feature

Candidate selection, durable voting/epoch state, prefix recovery, leader admission,
old-leader fencing, automatic rejoin and the public application path form one
correctness boundary. A role-field update alone is insufficient.

The design must extend or explicitly reconcile V5.0's entry/proof authority model.
Do not attach stock election rules to that model without checking their proof
obligations. Do not choose a leader simply by maximum stored index. Unproven
entries, durable proofs, installed snapshots and publication state are different.

Leader-read safety belongs in V5.1 because a new leader may commit while an isolated
old leader is unaware of its replacement. The published V5.0 runtime allows reads
of a previously published view after quorum loss, until a specified revocation
condition is detected; see [public runtime](v5.0/PUBLIC_ADMISSION_RUNTIME.md).
That legacy behavior must not be silently relabelled as a linearizable read in an
automated-leadership mode.

Recommended posture: retain the configured-leader behavior under an explicit
compatible mode, and use a separate opt-in automatic mode with an approved read
barrier. Exact API and format declarations remain Phase 0 decisions. Every operation
advertised as a strong read must establish the relevant current authority and
applied committed cut. Already-pinned historical snapshots, where supported, must
remain explicitly historical. A local role flag or stale diagnostic observation is
not an authority proof. No hidden downgrade is permitted.

Public consumers must exercise automatic recovery without manually activating the
surviving leader. Leader hints are discovery information, not permission to write.
Possible-dispatch timeouts remain indeterminate. Do not automatically replay such
mutations without an accepted, durably replicated deduplication protocol. Supporting
such a protocol is a separate scope decision, not an assumed V5.1 feature.

An explicit rejection proven to precede mutation admission and any dispatch can be
retried by the caller without duplicating that attempt. A timeout, leader hint or
later diagnostic does not establish that proof. Phase 0 must specify how the public
outcome distinguishes such rejections from indeterminate mutations; this proposal
adds no automatic retry policy.

### V5.2: explicit read policies

Freeze three distinct policies: the approved strong leader-read path,
stale-allowed reads of published committed state, and reads that wait until the
chosen replica has applied and published at least a required committed position.
Minimum-progress tokens must bind the group and compatible history identity, not
just a numeric index. Define restore, replacement, expiry and wrong-history errors.

A lower-bound progress token can support read-your-writes for a confirmed write;
it does not by itself certify freshness against all other clients. A timeout must
not silently return a stale result. Freeze cancellation, paging, pinning, failover
and wait-resource bounds. Reject unsupported combinations before consuming expensive
resources. Public reads must never expose merely appended or uncommitted state.

### V5.3: controlled operations

V5.0 already supports explicit same-NodeId disk replacement within its fixed
manifest; see [cleanup and replacement](v5.0/PUBLIC_ADMISSION_CONTRACT.md#cleanup-and-replacement).
That recovery operation does not add or remove a voter identity. V5.3 must separately
define changes to the voting configuration and their interaction with replacement.

A joining node should first catch up without changing the voting quorum. Promotion,
removal and replacement must then follow joint consensus or an equivalently reviewed
safe membership protocol, as required by the accepted charter.

Serialize membership transitions initially. Bind each operation to a configuration
identity and stable operation identity; define queryable progress, crash recovery,
repeated calls, stale plans, irreversible transitions and source cleanup. A minority
must not restore availability by unilaterally rewriting membership.

Same-version rolling restart is a separate capability from mixed-version rolling
upgrade. Upgrade support requires explicit API/wire/storage compatibility, feature
activation and failure/rollback rules. Unsupported mixed versions fail closed.
Neither a version label nor successful same-version maintenance is upgrade evidence.

### V5.4: stable replicated-group handoff

Exercise elections, reads, recovery and membership together under repeated crashes,
network partitions, delayed messages, slow storage, corrupt replicas, interrupted
transfer and maintenance. Check long-lived proof, promise, ancestry, snapshot,
request and diagnostic metadata, not only the main replication log.

Document finite supported bounds, admission/backpressure and exhaustion behavior.
No cleanup may destroy the sole required authority, and no replica lag may create
unbounded retention. Move from small fixed-rate baselines to separately defined
load sweeps, increasing corpora and longer runs. State the tested envelope rather
than promising indefinite operation without evidence.

## 4. Evidence rules for every new boundary

Correctness comes first: an independent history model, deterministic network
schedules, separate-process crash evidence and external public consumers must exist
before a production path can be accepted. For each invariant identify the observable
failure counterexample and the evidence that detects it. Model success is not a
claim that an implementation is formally verified.

Separate three kinds of measurements: correctness/recovery at a controlled load,
capacity/saturation exploration, and comparative performance. Freeze workloads,
seeds, corpus identity, warmup, run length, repetitions, error classification and
measurement windows before claiming canonical results. Record offered and completed
rates, queueing, rejections, timeouts and indeterminate calls alongside latency.
Report failover detection, election, activation, first durable write and first
successful strong read separately, with explicit start/end events.

The V5.0 baseline is 49 scenario executions on its exact source, not 49 distinct
fault types and not validation of future elections, replica reads or sharding.
Use new suite/preset/baseline identities for genuinely new boundaries. Retain failed
runs and distinguish administrative retries from clean uninterrupted sequences.

A cloud plan requires current read-only quota/IAM/cost checks, bounded ownership and
cleanup, retention and independent validation, and explicit paid-run authorization.
Old quota snapshots and historical allocations are not current authorization.
Do not create cloud resources while reviewing this addendum.

## 5. Proposed V6 entry gate

V6 design discussion may proceed alongside V5.x. V6 production implementation should
start only after an accepted V5.4 handoff, or an explicit reviewed change to that gate
showing equivalent prerequisite guarantees. Do not silently lower the gate to
'V5.0 has been published.'

The handoff should pin a published replicated-group baseline and provide: authority
and commit semantics; leader/read/client contracts; supported membership operations;
recovery and format compatibility; resource and process ownership; diagnostic and
failure classifications; and reproducible evidence. V6 should compose those groups,
not depend on private replica classes or invent another replication protocol.

## 6. Review status and references

| Review item | Status at proposal creation |
| --- | --- |
| Scope refinement approved | Pending |
| V5.1 Phase 0 contract approved | Not yet produced by this entry plan |
| V5.1 implementation authorized | No |
| V6 implementation authorized | No |
| Paid execution or publication authorized | No |

Primary design references, consulted 2026-09-19: [etcd API guarantees](https://etcd.io/docs/v3.6/learning/api_guarantees/)
for the distinction between linearizable and potentially stale reads, and
[etcd learner design](https://etcd.io/docs/v3.6/learning/design-learner/)
for non-voting catch-up before promotion. These are comparative references, not a
claim that GSE implements etcd's algorithm or inherits its guarantees.
