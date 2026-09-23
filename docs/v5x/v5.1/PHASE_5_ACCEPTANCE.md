# V5.1 Phase 5C: hardening acceptance and resource reconciliation

**Status:** full Phase 5 accepted through
[PR #214](https://github.com/patricklfdm/GeneralSearchEngine/pull/214) at
`15c8c68011e37370dfcd31ee855f91247c3771d8`.
[Master CI 35830149418](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35830149418)
passed the docs-only path; the unchanged runtime's full CI and original review below
remain bound to `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`. This closes Phase 5 within
its finite scope. The separate [Phase 6 entry](PHASE_6_ENTRY_PLAN.md) was accepted
through PR #215; its model foundation is the next implementation candidate.

## Exact source and acceptance chain

| Boundary | Protected source | Evidence |
| --- | --- | --- |
| Phase 4 A–P | `b0d586f32b01f59aadfa940d7f778a8a2b5ea078`, PR #208 | [CI 35802660895](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35802660895), [final coverage](PHASE_4_FINAL_COVERAGE.md) |
| Phase 5A | `04d12316bd6971ac477cfcb08c5073b2252ecf2a`, PRs #209–#212 | [CI 35818964327](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35818964327), [combined recovery](PHASE_5_COMBINED_RECOVERY.md) |
| Phase 5B / code reviewed here | `fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`, PR #213 | [CI 35826641489](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35826641489), [combined lifecycle](PHASE_5_COMBINED_LIFECYCLE.md) |

The last run passed **all 19 jobs**, including Required and every one of the
**23 V5.1 verification steps**. Full CI also passed reactor, V4/V5.0 regression,
compatibility, release-artifact, soak/examples and no-GCP cloud checks. This is an
exact-master result, not a branch-only result or a docs-only skipped build.

This Batch C changes documentation only. It reuses that full code validation and
replays its original evidence offline; it does not describe a new local JVM run.
The [reconciliation ledger](PHASE_5_EVIDENCE_LEDGER.md) binds the source,
source-inventory digest, common candidate JAR hashes, executed steps, six artifact
IDs/digests, expanded inventories and eight suite receipts. Artifact retention is
finite; this ledger is a review index, not a replacement for raw evidence.

## Coverage reconciled

Seven Phase 5 cases are supplemented by sixteen public and eight internal resource
cases already introduced in Phase 4. They do not inflate the number of new Phase 5
scenarios. The [E01–E12 map](PHASE_4_EVIDENCE_STATUS.md) remains the governing account
of other protocol, lifecycle and internal-boundary coverage.

| Suite | Cases | Layer and claim |
| --- | ---: | --- |
| `public-combined-hardening` | 3 | Held ACCEPT/PROOF ACK plus partition/crash; complete retained group restart. Three consecutive rounds per case on the same authorities. |
| `public-combined-lifecycle` | 4 | Torn ACCEPT/PROOF plus real outbound pressure and healthy follower restart; cancelled chosen write across failover; pinned read/close across recovery. |
| `public-lifecycle-hardening` | 5 | Pinned rebuild, two partial-write cases and repeated queued/exchange timeouts. |
| `public-transport-pressure` | 5 | Actual inbound/outbound saturation and slow leader/follower ACCEPT/PROOF force. |
| `public-runtime-backpressure` | 4 | Queued deadlines, query reentrancy, completion chaining and completion capacity. |
| `public-resource-exhaustion` | 2 | Real minority snapshot-staging and retained-budget refusal while the healthy majority continues. |
| `internal-resource-boundary` | 6 | Promise count, retained bytes, transfer staging, entry/ancestry count and epoch overflow. Internal store/model fixtures. |
| `internal-runtime-mailbox` | 2 | Deliberately fill input/completion mailboxes. Internal injection, not natural public saturation. |

Offline replay passed all 31 cases and rejected 349 evidence-negative variants,
plus six copied-path negatives. The ledger records actual call, process, archive and negative counts from this CI
run. Counts can differ from older local runs because classified unsuccessful calls
remain in the history; old local tables are preserved rather than rewritten.

## Independent replay and provenance

The offline review checks exact matrix membership, successful source-bound receipts,
identical tracked-file inventories and candidate JAR hashes across the eight suites.
It independently decodes retained authority and raw force/wire/application evidence,
checks chosen prefixes and successful read cuts, then reruns the bounded client
history search and case-specific schedule/resource/negative checks. Observer status
alone is never the correctness oracle. Histories include every attempted read/write,
including refusal, pending, cancelled and indeterminate outcomes. Lifecycle calls
retain their separate raw invocation/completion bindings.

Batch A permits at most 48 application calls per history, Batch B 32 and supporting
public suites 24; all retain the 100000-state search ceiling and fail if inconclusive.
Archive inventories, actual process starts/stops and PID-specific reservations bind
each retained restart. Torn tails must be explicitly classified and rejected.

Downloaded authority retains its original absolute CI seal path. Ordinary inspection
must reject these relocated copies: one copied-path negative per artifact is checked.
For forensic replay only, the existing `storage_inspector.inspect_archive` API checks
the immutable expanded inventory against the original CI path, reconstructed from
the exact artifact family and relative path, not trusted from the seal itself.
The temporary review adapter applies this mapping only while calling the existing
oracles. It neither edits seals nor permits copied directories to start a runtime.
Full downloaded file inventories must remain unchanged after review.

Local review files are under `target/v51-phase5-acceptance/`: `master-ci.json`,
`artifacts.json`, `ci-artifacts/`, `revalidate.py`, `revalidate.log` and
`revalidation.json`. The checked-in ledger is the compact summary. Its GitHub digest
is the archive-service digest; its expanded-inventory hash identifies the downloaded
file map. They represent different byte sequences and are not interchangeable.

## Resource accounting and limits

These are the reviewed implementation/fixture bounds, not new defaults or service
level promises. Read-only samples establish bounds at observed cuts; transport
reservation events additionally account for each admitted exchange over its lifetime.

| Resource | Reviewed bound and evidence |
| --- | --- |
| Public admission / ordered work / deadlines | Fixture permits four pending calls. A/B recovered-round samples require all four permits and zero pending, ordered and timer work. Cancellation cannot undo chosen authority or leak permits. |
| Runtime mailboxes | Input queue 32, completion queue 16. Internal 33rd/17th submissions exercise real rejection; the two cases stay separately classified from public histories. |
| Worker executors | Network: four active/four queued; application: one/four; client completion: one/two. Samples must stay bounded; they do not assert background work is always idle. |
| Transport | Eight inbound reservations; two outbound per remote peer, four across the two peers; four-frame byte budget (4 MiB for the 1 MiB fixture frame). Pressure must occupy real slots and produce matching rejection. |
| Reservation lifetime | Normal close releases all reservations. Only a recorded SIGKILL may destroy bounded live reservations for that exact PID. A new process cannot supply a missing old release. |
| Application views | Two current engines and at most two staged engines; pinned generations defer/reject further materialization. Pinned read/close retains ownership until release. No forced termination of a user callback is promised. |
| Snapshot staging | Public minority fixture seals 128 KiB staging; the actual transfer allowance is one quarter (32768 bytes). A real image exceeds that allowance, yielding SNAPSHOT_OFFER capacity rejection before chunks/install. |
| Retained bytes | Public minority fixture seals 128 KiB; two legal bulks produce an image larger than the entire bound. Raw admission accounting proves rejection independently of background generation cleanup. Healthy majority service survives retained restart; the exhausted voter need not regain service. |
| Other finite ceilings | Internal fixtures cover 10000 promises and overflow-safe epoch arithmetic. Entry/ancestry ordinal 1000001 is rejected by boundary fixtures; this is not one million successful live operations. Byte/metadata ceilings may bind earlier. |

Sources: [resource limits](PHASE_4_RESOURCE_LIMITS.md),
[backpressure](PHASE_4_BACKPRESSURE.md), [transport pressure](PHASE_4_PUBLIC_PRESSURE.md),
[lifecycle hardening](PHASE_4_LIFECYCLE_HARDENING.md) and
[API/resource contract](API_FORMAT_AND_COMPATIBILITY.md#resource-and-timing-bounds).
The generic 64 MiB complete-image and 10000-index ceilings remain existing contract
limits, not additional large-scale exhaustion runs performed by this review.

A/B use 1200 ms request and 9600 ms operation deadlines, 4096-byte chunks and bounded
60-second observer holds. Node 3 votes and recovers with its sealed 600000–601200 ms
election interval; the other two use 3600–6000 ms. These controlled schedules do not
measure production failover latency. Continuous loss of quorum can exhaust the finite
promise budget and fail closed; the evidence does not promise endless elections.

## Defect and failed-attempt disposition

- Phase 5A found a production rebuild defect: private reconstruction exceeded the
  engine's bulk limit. The accepted fix uses the smaller engine/storage limit;
  five regression cases preserve snapshot identity and unsplit client atomic bulks.
  The failing trace and local pre-fix results remain in the [A record](PHASE_5_COMBINED_RECOVERY.md).
- B's first torn/pressure schedule closed the damaged listener too early to occupy
  real outbound slots. The corrected fixed schedule retains its quarantined listener
  until pressure/recovery completes, forbids further forcing/publication, then
  archives and rejects both reopen probes. The failed attempt remains separate.
- PR #213 exposed an inherited post-crash test assumption: a cached READY observation
  was treated as four guaranteed immediate successes. The accepted driver requires
  one complete successful wave within three fresh unique-key waves, retains every
  intermediate result, and never resubmits uncertain writes. Unknown, integrity,
  storage and explicit capacity errors still fail. The original trace did not have
  enough reservation accounting to prove a specific contention mechanism; this
  review makes no stronger diagnosis. See the [fault-driver record](PHASE_4_PUBLIC_FAULTS.md).

Other inherited CI fixes retain their own records in the acceptance chain; a rerun
success is not substituted for those fixes or for retained failure evidence. The
present replay found no additional failed evidence or required production change.

## Batch C validation

- Original exact-master CI: all 19 jobs and 23 V5.1 verification steps passed.
- Offline forensic replay: 31 cases passed, 349 evidence mutations rejected and
  six ordinary copied-path inspections rejected; original inventories unchanged.
- Local foundation gate: version alignment, accepted V5.0 contract, V5.1 43-document
  contract, all 267 Python tests and independent model/format evidence passed.
- CI classifier/topology/Required tests: 19 passed. All twelve changed/new files
  are Markdown and classify as documentation-only; standard push/PR CI can use
  the lightweight path without another reactor build.
- All changed/new Markdown local targets, anchors, fences and whitespace passed.
  Accepted charter, published controls, production code, tests and workflows are unchanged.

The local foundation output is `target/v51-foundation/run.3qTMEU/evidence`;
review logs and `docs-validation.json` are under `target/v51-phase5-acceptance/`.
These checks supported the review; the subsequent protected acceptance is recorded
at the top and does not relabel the original runtime measurement source.

## Acceptance boundary and next entry

Phase 5's finite combined-fault and resource obligations are reconciled and accepted
through PR #214. It does not establish exhaustive
arbitrary schedules, indefinite endurance, host power-loss behavior, hostile-network
safety, throughput/SLA targets, physical scaling or paid-cloud acceptance. Fixed
three-voter membership, leader-only reads and published V4.4/V5.0 controls remain.

The subsequent [accepted Phase 6 entry](PHASE_6_ENTRY_PLAN.md) follows this accepted handoff:

1. Freeze corpus/seed, operation mix, offered rates, measurement windows/repetitions
   and fault schedule; distinguish automatic strong-read NO_OP cost from V5.0 reads.
2. Bind exact candidate/control artifacts and source. Define independent outcome,
   chosen-prefix and query-cut evidence; use bounded full-history search only where
   its admitted size permits it. Keep all timeouts/rejections in the outcome account.
3. Define detection, election, activation, first post-fault read/write and client
   outage measurements using the existing [clock/causality rules](TESTING_AND_EVIDENCE.md).
   Freeze numerical criteria before canonical execution, not after observing results.
4. Qualify local/fake-cloud machinery first. Paid work needs new source/image/IAM/
   quota/retention/cleanup/cost preflight, three simultaneous voter VMs and explicit
   user initiation. Prior V5.0 budgets, sequences or cleanup receipts are not new
   authorization. Keep exact ownership/lease/resource-ID cleanup checks.

Follow the [Phase 5 checklist](PHASE_5_CHECKLIST.md). No cloud experiment, release,
commit, push or merge is performed by this review.
