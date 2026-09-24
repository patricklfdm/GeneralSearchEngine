# V5.1 Phase 6C1 remote control foundation

**Status:** accepted through PR #223 at master
`833da4947266b4edfbee2a0e6fe10055ed3be00c`. Exact-master CI
[35942555519](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35942555519)
passed all nineteen jobs and 25 V5.1 verification steps.
[6A](PHASE_6_LOCAL_ACCEPTANCE.md) and [6B](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md)
are accepted through PR #222, exact-master CI `35937300754`: nineteen successful
jobs and 24 successful V5.1 verification steps. That earlier CI preceded the 6C1 implementation.

The frozen workload hash remains
`bee0b38ae20611a0d36259e554c5d03b1e1ebd87fc71ab648b3848681854754a`.
This batch implements reusable guest/control components and qualifies their
failure behavior. Its receipt explicitly says `local-remote-control-only`,
`engineWorkloadExecuted=false`, `fullRemoteQualification=false`, `paidCloud=false`.
It supplies no paid workflow, provider credentials or V5.1 cloud admission.

## Review boundaries inside 6C

| Boundary | Implementation and required evidence |
| --- | --- |
| 6C1, accepted | Durable command ownership, original-deadline query after lost replies, fixed arrivals, disjoint time accounting, binary evidence collection; real subprocess crash/cancel and deterministic scheduler negatives. |
| 6C2, in progress | Connect persistent guest JVM commands to all three immutable control/candidate classpaths; execute complete healthy/read-heavy/sustained tapes and twelve fault cells; independently bind concurrent rich reads to actual captured cuts; full-size slots, basis/transfer, pin and two-generation retention checks. |
| 6C3 | Own prepare/run/collect/validate/cleanup; same-path fake provisioning/SSH/upload/credential/deletion failures; source-bound runner/workflow/WIF/environment/price/cleanup identities and fresh configuration review. |

These are implementation review boundaries within the existing
[6C exit](PHASE_6_ENTRY_PLAN.md#ordered-delivery). Full Phase 6C stays unchecked
until all three are accepted and exact-source full CI/configuration pass. A
component or worker PASS cannot replace complete workload/physical qualification.

## Durable command receipt

[`remote_command.py`](../../../scripts/v51/remote_command.py) binds each store to
source SHA, bundle digest, attempt ID, voter and frozen workload hash. These fields
are identity checks, not evidence of release qualification or paid admission.
The future trusted launcher must independently verify the complete bundle bytes.
No command supplies a shell command or arbitrary argv; a trusted, explicitly
supplied handler implements the allowed lifecycle/window/fault/collection names.

An exclusive executor lock serializes command handlers. Before handler entry it
creates and fsyncs the command directory, exact request and started receipt. The
command ID is consumed even if execution dies between directory creation and the
first persisted request. Reusing the ID with different bytes fails. Reusing the
same request only reads its existing receipt, including after process restart.
The store retains PID, Linux start ticks and boot ID; no other process's clock is
subtracted from these guest monotonic observations.

A terminal receipt is forced and atomically published before returning it. Polling
sees either an absent receipt or its complete JSON; interrupted publication retains
the temporary bytes and consumed command ID. A missing/torn receipt is not
permission to invoke the handler again. `RUNNING` after a dead process or
`UNCERTAIN` after an incomplete claim stays unresolved. The controller submits
once, then only queries the exact request until its original deadline. Repeated
query connection failures may use refreshed credentials in the transport adapter;
this component does not itself implement GCP credential renewal. A `NOT_FOUND`
query after a lost submit response also does not authorize resubmission.

Cancellation is a separate forced marker readable while the handler runs. Handlers
check it cooperatively and retain original dispatched outcomes. A cancellation
racing a completed handler retains that handler result under `CANCELLED`; it never
manufactures a safely retryable mutation. Killing a process cannot reveal whether
an already dispatched engine call committed. The later workload controller must
stop the case on unresolved command ownership and preserve that uncertainty.

Requests are bounded to 64 KiB and receipts to the frozen 4 MiB response ceiling.
A store accepts at most 2000 command IDs as a local metadata guard; the workload's
stricter public-operation, file and aggregate evidence bounds still apply. The
handler's original raw history remains separate from its bounded response.

## Guest schedule and independent dispatch evidence

[`remote_schedule.py`](../../../scripts/v51/remote_schedule.py) derives every call
from the hash-validated 6B generator. Its public entry accepts cell/preset/window;
it exposes no speed multiplier or caller-supplied time limit. One warmed executor
per lane admits at most one outstanding operation in that lane, up to four lanes.
Calls are scheduled in the issuing process's monotonic clock. Later integration
must invoke persistent local JVM IPC, with no SSH call per application operation.

Late arrivals, busy lanes and delayed executor entry produce retained
`NOT_DISPATCHED` observations. Failed operations stop subsequent dispatch without
replay. A successful window lasts its entire scheduled duration; draining cannot
extend its ten-second allowance. Four-lane burst dispatch spread is checked against
the original ten-millisecond bound. Unfinished operations remain visible and late
completion cannot retroactively turn their window green. The issuing process's
supervisor must enforce the cell deadline and reap a callback that does not return;
Python cannot safely kill one hung thread. Scheduler intervals describe callback
entry/return, not automatically the inner Java API latency or actual engine overlap.

[`remote_schedule_evidence.py`](../../../scripts/v51/remote_schedule_evidence.py)
independently checks frozen arrivals, bounds, raw transition coverage, lane ordering,
clock order, original outcomes and the final verdict. It reports
`engineSemanticsQualified=false`. It does not call the old two-field history checker
or claim that a dispatch receipt proves a rich read's captured prefix. The 6A
single-caller physical oracle still needs an explicit concurrent ownership path.

## Time accounting

[`remote_budget.py`](../../../scripts/v51/remote_budget.py) charges every interval
in one controller clock. Time outside named stages is control overhead; in-cell
SSH, startup, boundary, drain and close time remains inside that cell. Stages
cannot nest or restart their deadlines. Unused allowance never extends another
stage, and operation grace never increases the 5400-second measurement lease.
Cleanup is still entered after a failed stage; a late cleanup remains a recorded
failure rather than a reason to skip deletion. This ledger reports time, not proof
that any cloud deletion was performed. The provider adapter must supply exact-ID
absence evidence separately.

## Binary collection

[`remote_collection.py`](../../../scripts/v51/remote_collection.py) streams a
complete archive into 8 MiB binary parts, at most 256 / 2 GiB compressed. JSON
responses carry only bounded part metadata. Every part and every raw member has
an exact size and SHA-256. Packing checks source inventory before and after;
collect only quiescent evidence, with the runtime already stopped.

Receiving an interrupted part leaves its partial file intact. A fresh download
attempt may fetch the same immutable evidence bytes; it never re-executes the
workload. Extraction requires the exact complete part set, then rejects path
traversal, links, non-regular members, duplicates, missing/extra members, wrong
attempts, hash changes and budget overflow. Expanded/member/file/trace limits come
from the unchanged 6B plan. All `.jsonl`/`.log` members count toward the archive
trace limit; the guest producer still must enforce the per-node/cell trace limit
and required resource samples when 6C2 integrates engine traces.

## Local qualification and limits

```bash
scripts/verify-v51-phase6-remote-foundation.sh
```

The gate retains source hashes, immutable commands, child outputs, process cleanup,
full synthetic scheduling traces, receipts and replayed binary evidence under
`target/v51-remote-foundation/run.*/`. The raw receipt only marks
`CONTROL_CHECKS_PASSED`; `evidence-result.json` records final PASS after complete
collection and replay, or FAIL if retention fails. It runs without Maven or GCP
credentials.
CI places it in the existing `Cloud runner (no GCP)` job with always-uploaded
fourteen-day local artifacts. Paid evidence's thirty-day retention remains a
separate unimplemented cloud requirement.

Real subprocess cases cover a lost submit response, a second process submitting
the same command, SIGKILL after a forced handler-entry record, and cancellation
after handler entry. The synthetic handler performs a durable diagnostic append;
it does not pretend that append is a GSE mutation. Every process is reaped.
Deterministic guest clocks execute all 650 planned arrivals across the two healthy
presets and both concurrent tapes through the same scheduling state machine.
These clocks qualify accounting, not real arrival rates, engine overlap or a full
cloud runtime. Separate tests exercise actual four-thread callbacks, the real
8 MiB part boundary with incompressible data, and rejection at budget/identity/
archive/cancellation/deadline boundaries.

The following [6C2A rich-workload candidate](PHASE_6_REMOTE_RICH.md) connects the
three real JVM modes and concurrent read oracle. Its protected CI and the full
6C2/6C3 exits remain required. Published
controls, production Java, V5.0 cloud workflows, workload parameters, cost ledgers
and manually triggered paid execution are unchanged.

### Candidate validation record

Local gate `target/v51-remote-foundation/run.Bhlv33/evidence` passed its five
control/accounting cases and complete 35-file collection replay. All 408 V5.1
Python tests, including 55 focused remote regressions, passed. The 27 CI/toolchain
tests, 116 workflow shell blocks, unchanged original steps/job identities,
documentation contract, 533 local targets, ten anchors and whitespace checks also
passed. `target/v51-remote-foundation/validation-summary.json` indexes retained
logs and receipts. Production Java and immutable plans/controls were unchanged;
no full Maven reactor or paid workload was rerun for this control-only batch.
