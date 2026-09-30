# V5.1 Phase 5B: quarantine, pressure and recovery lifecycle

**Status:** Batch B accepted through PR #213 at master
`fc1feca4dee6ee346e45d3afb22c4df9b9e0d945`,
[exact-master CI 35826641489](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35826641489),
all 19 jobs passed. The original local record below remains bound to its Batch A
base plus working-tree implementation. [Phase 5C](PHASE_5_ACCEPTANCE.md) reconciles
the exact-master evidence and is accepted through PR #214, completing Phase 5.
The separate [Phase 6 entry](PHASE_6_ENTRY_PLAN.md) is now a candidate.
See the [checklist](PHASE_5_CHECKLIST.md).

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
hardening/resource evidence accepted through PR #214; Phase 6 remains a separate entry.

## Post-PR-260 correction: retained promises during the final recovery write

[Master CI 36687338735](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36687338735/job/109798029294)
on `ebafd20c0e3e40b584904b9b817344e4fd05a88b` failed
`cancel-chosen-recovery`; the other three combined lifecycle cases passed.
The retained trace shows node 1 complete its epoch-5 strong read, then begin the
new bulk write. Restarted node 2 returned an epoch-6 retained promise in a
HEARTBEAT rejection while that write was in progress. Node 1 correctly reported
`INDETERMINATE / STALE_EPOCH`. The driver still required the first write after the
read to succeed. A completed read certifies its own cut; it cannot reserve
leadership for the next operation. PR #260's cleanup credential changes did not
change this driver or the replication runtime.

The original failed artifact remains under
`target/v51-combined-lifecycle-ci-36687338735/artifact/run.4jDc7u/evidence/`,
with the decoded timeline in the adjacent `diagnosis.json`. Its partial public
history passed independent replay, but that does not qualify the failed scenario.

Phase 5B now uses the existing
[Phase 5A bounded recovery rule](PHASE_5_COMBINED_RECOVERY.md) for the final
read/write stage:

- At most three **different** bulks use keys `80/81`, `82/83`, then `84/85`.
  Each starts after a fresh successful strong read; read acquisition keeps the
  existing four-attempt bound. Earlier scenario writes still require immediate
  success. The complete case retains the 32-application-call and 100000-state
  limits, with a dispatch guard before the bounded read/write helpers send work.
- Every attempt and its original outcome remain in the public history. Only the
  existing classified availability refusals can advance to another fresh bulk.
  An uncertain bulk is never replayed. A subsequent read may observe its entire
  chosen bulk or its absence; partial, changed or reordered results fail.
  Integrity, storage, capacity, unknown and disconnected outcomes still fail.
- The independent validator accounts for every recovery read/write, checks the
  fixed key tape, process identity, ordering, classified outcomes and exact final
  projection. For torn cases the recovery boundary follows the pressure-overlap
  read after restart; for lifecycle cases it follows the retained restart after
  the majority read. Moving the declared boundary cannot hide a failed attempt.
  Raw client, physical quorum/proof and complete history checks still apply.
- Four additional negative variants per case remove a recovery attempt, change
  or replay its keys, move its boundary, or forge its final projection. The full
  matrix therefore requires 76 rejected variants, including the original 60.

This correction changes Python qualification and its evidence checks. Sealed
resource/deadline bounds, fault placement and runtime Java remain unchanged.
Corrected-source protected CI is still required; local verification does not
advance Phase 6 cloud admission or acceptance.

Local correction validation:

- Two deterministic regressions reproduce the original immediate-write failure
  with both chosen and absent uncertain bulks. After the correction all 63 focused
  tests pass, including 11 new recovery driver/independent-checker tests and the
  existing Phase 5A helper tests.
- The complete four-case gate passed at
  `target/v51-combined-lifecycle/run.qefPcC/evidence/receipt.json`: application
  counts were 14, 14, 11 and 14 in the scenario order above; all 76 negative
  variants were rejected. This live matrix completed each final recovery write on
  its first attempt; the classified-failure paths are exercised deterministically.
- The reactor was repackaged with tests skipped because this correction changes
  no Java. Maven kept the identical JAR's old timestamp, so the previous package
  was retained separately before regeneration; the replication SHA-256 stayed
  `b289d17088415d9fb1e6589321bd5f47bf9fd612d867d7487f64f10082ffa9d3`.
  The freshness guard was not relaxed. Both pre-execution freshness refusals
  remain in the validation logs.
- Documentation links/contract, shell syntax and whitespace checks pass.
  Logs, the red/green regression record and validation summary are under
  `target/v51-combined-lifecycle-recovery/`. Protected CI for the corrected source
  remains pending.
