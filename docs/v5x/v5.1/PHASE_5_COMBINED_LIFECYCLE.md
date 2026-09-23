# V5.1 Phase 5B: quarantine, pressure and recovery lifecycle

**Status:** Batch B accepted through PR #213 at master
`fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`,
[exact-master CI 35826641489](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35826641489),
all 19 jobs passed. The original local record below remains bound to its Batch A
base plus working-tree implementation. [Phase 5C](PHASE_5_ACCEPTANCE.md) reconciles
the exact-master evidence; full Phase 5 protected acceptance and Phase 6 entry
remain separate. See the [checklist](PHASE_5_CHECKLIST.md).

## Fixed scenarios (before execution)

Each case bootstraps one three-voter public group and keeps its GroupId and voter
identities. The controller never repairs authority or replays uncertain writes.
All cases use the admitted backpressure profile: four public pending operations,
1200 ms request / 9600 ms operation deadlines and 4096-byte snapshot chunks.
Node 3 votes normally with the existing 600000–601200 ms election interval;
the other voters use 3600–6000 ms. Setup briefly drops their PREPARE requests
to node 3 until the first leader exists, then heals before the seeded baseline.
This keeps the torn quorum peer among the two campaigning voters. Histories are bounded to 32 application calls
and 100000 independent linearizability search states. Holds retain their existing
60-second observer bound and recovery waits remain finite.

| Case | Required combined schedule |
| --- | --- |
| `torn-accept-pressure` | Interrupt a real leader ACCEPT append after 64 bytes. Preserve the indeterminate result and require quarantined public refusals; keep its failed runtime listener alive. Hold both outbound slots from the healthy leader toward the quarantined voter; require a real capacity rejection. Restart its only healthy follower (node 3) on retained authority while pressure remains held. The two healthy voters must recover and serve a new write/read before pressure release; the incomplete bulk must remain absent. Then close and archive the quarantined voter, require unchanged bytes throughout pressure, and reject two independent retained startups. |
| `torn-proof-pressure` | Interrupt the actual quorum follower's PROOF append after 64 bytes. Apply the same quarantine/leader-pressure/follower-restart schedule. The already chosen indeterminate bulk must survive recovery and all subsequent reads. |
| `cancel-chosen-recovery` | Hold an ACCEPT_ACK after its response is read, cancel the original public future, and partition the old leader. Require the surviving majority to recover the chosen cancelled bulk and serve another write/read while the ACK is still held. Heal, observe a higher promise on the old voter, release the stale response and retain-restart that voter. Cancellation must not undo the chosen value or turn into a successful original response. |
| `close-pinned-recovery` | Hold a captured old-leader read; partition it and advance the majority. Heal and require a newer snapshot to install while the old read remains pinned. Close the old handle during recovery, require a bounded deadline result and refusal of a duplicate owner, while the majority continues serving. Release the old read with its original view, finish close, archive and restart the retained voter, then read/write the new prefix. |

## Required evidence

- Independently inspect force/wire/quorum/application bytes and every successful
  read barrier; check all public outcomes and one complete history per case.
- Bind each process generation, stop, immutable pre-reopen archive and restart;
  neither damaged authority nor its rejected-startup probes may become a source.
- Bind the exact torn append to its observed failure, immutable quarantine archive
  and both rejected startups. The damaged voter must stop forcing/publishing;
  its listener remains alive solely to reach the real connect-before-write
  pressure boundary, and public read/write refusals precede that pressure.
- Count per-process transport admissions/releases and enforce actual limits.
  Pressure needs two real occupied peer slots, a matching rejection and public
  service on the healthy majority before release. Normal close must drain every
  reservation; no artificial accounting reset is permitted.
- Bind read-only queue/permit/timer samples to observer rows and require zero
  pending public work, ordered/timer queues and all four permits after recovery.
- Negative evidence must reject altered fault boundaries, hidden quarantine or
  restart failures, missing pressure/recovery overlap, changed cancellation/close
  outcomes, lost prefixes, borrowed archives/processes and leaked reservations.

This is bounded local combined-fault evidence, not host power-loss, arbitrary
schedule, endurance, paid-cloud or new public API evidence. Failed attempts remain
separate from the final complete matrix.

## Development schedule correction

The first complete local attempt kept both torn cases as failures: closing the
quarantined endpoint before pressure caused connection refusal before the
`BEFORE_REQUEST_WRITE` hold, so no real slots could remain occupied. The corrected
schedule keeps the already failed listener alive until healthy follower recovery
and pressure release, then closes/archives it and probes rejected reopen. Its
bytes must remain unchanged and no subsequent force/publication is allowed.
Cancellation and pinned-close cases passed in that original attempt. The failed
matrix is retained separately; it does not qualify Batch B.

## Local validation

The complete gate passed at
`target/v51-combined-lifecycle/run.iJOhYu/evidence/receipt.json`. Its recorded
runtime, scripts and workflow hashes match the final implementation; subsequent
documentation edits record the results. Every scenario starts a separate group,
executes one fixed schedule and retains its complete history and source inventory.

| Scenario | Runtime JVMs | Application calls | All public calls | Rejected retained startups | Rejected evidence variants |
| --- | ---: | ---: | ---: | ---: | ---: |
| `torn-accept-pressure` | 4 | 14 | 14 | 2 | 15 |
| `torn-proof-pressure` | 4 | 14 | 14 | 2 | 15 |
| `cancel-chosen-recovery` | 4 | 11 | 12 | 0 | 15 |
| `close-pinned-recovery` | 4 | 14 | 18 | 0 | 15 |

Each case closes and archives one healthy voter before its retained restart.
Each torn case additionally closes/archives the quarantined voter and runs two
fresh rejected-startup JVMs. The application history includes all read/write
attempts, including rejections, cancellation and indeterminate results; lifecycle
calls are separately bound to raw invocation/completion observations. The sixty
negative variants must all fail validation.

- Reactor package: 862 tests, 858 passed and 4 skipped, zero failures/errors.
  The tested JARs were repackaged with identical SHA-256 after Maven preserved old
  timestamps on unchanged bytes; the existing freshness guard was retained.
- V5.1 Python discovery: 257 tests passed, including 12 new overlap/accounting
  unit tests; the new gate's focused unit invocation passed 24 tests.
- Existing public recovery `close-pinned` case passed with the shared consumer's
  optional read-only diagnostic sample; production Java remains unchanged.
- Foundation gate passed its independent model/format checks. Final documentation
  checks cover 43 documents; CI classifier/topology/Required checks passed 19 tests.
- Workflow validation: 19 jobs, 114 shell blocks, 46 unique artifact names. The new
  gate and always-retained upload run in `v51-admission-resources`; all seventeen
  full-CI jobs remain required. Hosted gate duration remains to be measured.

Local summary and logs are under `target/v51-combined-lifecycle/`, including
`validation-summary.json`, `reactor.log`, `python-tests.log`, `ci-tests.log`,
`foundation.log`, `regression-close-pinned.log` and `qualification.log`.
The first failed full matrix is preserved under `run.NK8wYB/evidence`; the earlier
freshness-guard refusal is under `run.kHXxgv/evidence`. The corrected targeted
ACCEPT run under `dev-torn-accept-v2` passed before the final full matrix. None of
these development attempts is relabelled as complete qualification.

The protected acceptance at the top supersedes this original pending Batch B record.
PR #213 also corrected the inherited post-crash concurrent-wave driver; its
[classified, bounded progress rule](PHASE_4_PUBLIC_FAULTS.md) preserves every
intermediate outcome and never replays an uncertain write. The exact-master
[Phase 5C review](PHASE_5_ACCEPTANCE.md) covers that correction and the complete
hardening/resource evidence before full Phase 5 acceptance or Phase 6 entry.
