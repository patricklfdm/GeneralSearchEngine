# Native drill startup correction and flexible member order

**Status:** startup/order correction accepted through PR #312; snapshot-repeat
correction accepted through PR #313, master
`eaa80316a3e45de437c521f07c64b6d7f0b130b6`, protected CI `38097928287`.
The staged-startup correction below is a local candidate, 2026-10-11;
corrected-source protected CI and complete paid qualification remain pending.
Full Phase 6 remains open.

## Staged bounded-voter startup

PR #313 merged at `eaa80316a3e45de437c521f07c64b6d7f0b130b6`;
protected master CI `38097928287` passed all 46 jobs on attempt 1.
The subsequent native drill [38109891402](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38109891402)
executed eleven cells, then failed the final cell before any workload call.
After the original three-way PREPARE heal, node 3 was `LEADER_READY` at epoch 10
in seven consecutive controller observations. Both healthy voters were followers.
Waiting longer could not require that legitimate elected leader to step down.

The 180-second startup wait ended during a status query with only 2.75 seconds
remaining. Its retained guest terminal receipt is `SUCCEEDED` (3.66 milliseconds
of guest execution), while the controller reported `RUNTIME_COMMAND_UNRESOLVED`.
All JVMs subsequently exited normally; traces were about 1.2–1.8 MB, without the
previous trace-capacity failure. Cleanup confirmed all thirteen resources absent,
retention was `VERIFIED`, and the lease was released. Original artifacts, decoded
traces and diagnosis are retained under `target/v51-failure-drill-38109891402/`.

A first local correction released healthy PREPARE senders before node 3. The
complete SSH drill with a twelve-second delayed node-3 startup exposed another
required invariant: the healthy leader could select node 3 as its **fixed write
partner** even though node 3 was a follower. Isolating that partner then made the
first large bulk `INDETERMINATE / QUORUM_UNAVAILABLE`. The original failed local
run remains at `target/v51-bounded-voter-startup/owned-delayed/`; it is not accepted.

The final initialization barrier lets healthy PREPARE requests reach node 3 and
fence its campaign, while dropping their responses at the healthy sender. Node 3's
own outbound PREPARE remains blocked. Thus node 3 can promise the current healthy
ballot without supplying the first complete basis that fixes the write pair.
The controller requires both healthy voters in the original `PROMISE_QUORUM`
selection and a same-epoch healthy leader/bounded follower before releasing the
barrier, then repeats both checks before the first seed mutation. Either healthy
leader remains eligible. The shared-host fault entry uses the same request/response
routing and selected-pair check; it no longer pins the earlier leader.

Status queries to different guests run concurrently; each guest still has one
serialized command executor. Both checks, their selection observations and all
heals share one original activation deadline, clipped to the cell limit. Watchdog
releases fail admission. A command exhausting that deadline retains its original
receipt/failure and cause, but reports `RUNTIME_BOUNDED_VOTER_FENCING`; last
observed states remain in the cell receipt. Earlier transport errors still fail.
Independent replay binds role and selection observations to original receipts and
traces, checks the fixed healthy pair and epoch, and requires both observations
around the complete PREPARE heal before seeds. Missing, fabricated, wrong-role,
wrong-pair, wrong-epoch, reordered and late observations cannot qualify.

The delayed local failure also showed that stopping a failed cell while its data
fault remained held could reject later collection as `fault still isolated`.
After the JVM is confirmed closed, stop now releases remaining local injections
with an emergency/watchdog marker. Original stop failures still propagate, and
that marker cannot substitute for the scenario's original heal or make failed
work qualify. This preserves diagnostic collection without waiting for a timer.

The final-cell audit covers seed catch-up, heartbeat-preserving data isolation,
real 128-KiB capacity refusal/accounting, once-only retained restarts of node 3 and
a healthy leader, post-restart strong reads, original-command collection, immutable
retention and exact-resource cleanup. No runtime Java, sealed workload/capacity/
timing contract, budget ledger or paid dispatch changes. Corrected-source protected
CI and all five same-source native members remain required.

Local verification of this correction:

- Complete pinned-Java reactor: 923 tests, four existing skips, zero failures or
  errors. The final guest package was rebuilt after all 103 required Java
  prerequisite tests passed. Runtime Java is unchanged by this correction.
- 190 related Python tests passed, covering startup, original evidence,
  diagnostics, shared fault cleanup, native timing and canonical reuse. The new
  bounded-election regression fails against the original startup implementation.
- Complete real JVM/TCP/SSH drill: all twelve cells, 103 public calls and 129
  evidence-negative variants passed. Every one of 663 command submissions lost
  its original reply deliberately and was resolved without submitting it twice.
  The final cell included a twelve-second node-3 startup delay; both observations
  showed node 2 leading at epoch 3 with the healthy fixed pair. Real capacity
  refusal, both retained restarts and three final strong reads completed in
  58.102 seconds, including the injected delay.
- Collection covered all 36 guest services; immutable retention read-back was
  `VERIFIED`, all thirteen modeled resources were absent and the lease released.
  Local paths were separate on one filesystem. This run does not establish mount
  isolation, GCP/IAP behavior or paid acceptance.
- Replaying the retained archive after unpacking into a new directory reproduced
  the exact twelve-cell result, including all 103 calls and 129 negative results.
- The shared-host targeted capacity cell also passed with twelve seconds of
  delayed startup, followed by exact independent replay after archive relocation.

Evidence and the final replay result are indexed at
`target/v51-bounded-voter-startup/validation-summary.json`. The earlier failed
local correction and original paid failure remain retained separately.

## Follow-up: repeated snapshots exhausted fault telemetry

Native drill [38033332912](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38033332912)
completed the first eleven cells. The final `minority-capacity` cell passed the
corrected startup check, seeds, real bounded-voter rejection and a healthy
post-rejection write/read. It subsequently lost its healthy node-2: the fault
observer hit `remote fault trace per-node bound`, failed its sampler and exited.
The next strong read returned `QUORUM_UNAVAILABLE`; the controller could not
complete the required retained-restart sequence. Independent replay correctly
rejected the incomplete cell.

Node-2 retained 134,214,593 bytes of trace, just below the 128-MiB limit because
the next append was rejected before publication. It recorded 230 completed
snapshot installations of nine distinct snapshot hashes; one 110,361-byte
snapshot was installed 87 times. `AutomaticRejoin.catchup` previously sent a
snapshot on every maintenance cycle when the peer's proven index equaled the
local cut. Full snapshot/chunk observations amplified those repeated transfers.
The cell took 422.373 seconds of its 600-second allowance; the complete budget
receipt was PASS. Cleanup confirmed all thirteen exact resources absent,
retention was VERIFIED and the lease was released. The original bytes and
diagnosis remain in `target/v51-failure-drill-38033332912/`.

The correction remembers at most one **exact acknowledged installation** per
remote voter, in maintenance-worker memory. A fresh status probe still runs on
every cycle. An identical ballot and snapshot digest, equal peer proven index
and the prior exact `REJOIN_INSTALL` response permit skipping that redundant
transfer. Equal progress alone is insufficient: an unconfirmed install, changed
snapshot/ballot or lagging peer must run the complete exchange. Higher promises
still fence the sender; failed probes still fail; fresh controllers inherit no
completion cache. No wire/durable format, proof, voting, publication, recovery
floor or cleanup rule changes. Follower publication remains distinct from durable
snapshot installation.

Fault-JVM EOF handling now inspects only a bounded stderr tail for the exact
observer exception line. It propagates the closed `RUNTIME_TRACE_CAPACITY` code
through the original failed command to the Runner summary. Unknown text is not
promoted, raw stderr is not exposed in that summary, and neither the command nor
workload is resubmitted. Original stderr and traces remain retained. The existing
128-MiB per-node trace and 32-MiB archive-member ceilings remain enforced; no
records are truncated, sampled away or silently dropped.

Deterministic regressions cover repeated idle cycles, lost/malformed install
ACKs, altered same-index snapshots, higher promises, new cuts, peer regression,
ballot changes, failed probes and fresh controllers. A subprocess regression
checks EOF-to-Runner diagnostic propagation without a second submission,
including clipped and unrecognized stderr lines.

Local verification on the correction:

- Complete pinned-Java reactor package: 923 tests, four existing skips, no
  failures/errors; all six new Java regressions pass. The old implementation
  failed both duplicate-transfer assertions (101 rather than one installation,
  and an unnecessary fourth transfer after the third transfer was confirmed).
- 115 focused Python checks pass. The 142 supplementary owned-service/workload
  checks passed across the initial run and two receiver-ownership checks rerun
  outside the sandbox's synthetic ancestor ownership; no permission guard changed.
- Real-TCP rejoin gate: all six cases, five runtime evidence negatives and seven
  recovery evidence negatives pass, including retained restart, a second failover,
  exact-cut witness exchange and repeated three-voter reclamation.
- Complete local fault gate: all twelve cells, 103 calls and 41 evidence negatives
  pass, followed by exact independent replay after archive pack/unpack. The
  `minority-capacity` cell observed the real rejection and completed both retained
  restarts. Its largest node trace was 8,757,228 bytes; no generation/ballot/snapshot
  identity was installed more than once. These local sizes are observations, not
  a cloud performance estimate.

Receipts and hashes are indexed in
`target/v51-rejoin-snapshot-repeat/validation-summary.json`, with the full local
fault receipt at `target/v51-remote-faults/run.gn8PLP/evidence/receipt.json`.
Those local checks preceded PR #313's protected acceptance. Native full-preset
acceptance is still open; the subsequent startup failure is recorded above.

## Retained failure and cause

PR #311 merged at `99df69f1d5c50daae8690f2ed4237482b0e88830`;
[master CI 37957278096](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37957278096)
passed on attempt 2. The full-preset native experiment
[37970604996](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37970604996)
passed. The subsequent native failure-drill
[37981974124](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37981974124)
executed eleven cells, then failed `minority-capacity` during initial fencing.
The failed cell had no workload calls. Its 259.324 seconds were below its
600-second cell ceiling; the original 180-second fencing wait expired.

Before starting the bounded voter and healing PREPARE traffic, node-2 was the
healthy leader at epoch 3. After healing, node-1 became `LEADER_READY` at epoch 5;
node-2 and node-3 were followers at epoch 5. The controller retained the old
node-2 choice and only polled node-2/node-3. Retained node-1 trace samples show
it ready for about 196 seconds before shutdown. A deterministic replay of these
observations reproduces the original failure.

All 46 guest commands completed successfully. Cleanup confirmed all thirteen
exact resources absent, with no leftovers; retention was `VERIFIED` and the lease
was released. The conservative ledger total after this attempt was USD 110 / 200.
Original failure evidence remains at `target/v51-failure-drill-37981974124/`,
including `diagnosis.json`, downloaded receipts and decoded member traces.

The correction observes both healthy voters and the bounded follower after heal,
and returns the single observed healthy leader sharing the follower's epoch.
All observations use one original absolute deadline, clipped to the cell limit;
late replies cannot satisfy it. No election is forced or mutation replayed.
The exact timeout now maps to `RUNTIME_BOUNDED_VOTER_FENCING`, with a closed safe
description instead of unclassified or raw exception text. An observed leader
can still change later; normal workload/history validation remains mandatory.

## Operator-authorized member-order amendment

The operator requested that all five members may start in any order. New native
v3 sequences can select **`runner_order=any-order`**, now the workflow default.
The paid execution selector still defaults to `off`. Any of `experiment`,
`failure-drill`, `canonical-1`, `canonical-2`, or `canonical-3` may be first or next
if it has not already passed in that sequence.

- A complete set still requires all five distinct members on the same source,
  archive, configuration, frozen workload and timing-plan identity. A partial set
  cannot close Phase 6.
- Canonical member numbers fix repetitions and control hosts 1/2/3. They do not
  depend on execution position. Cell order and all measured parameters remain
  frozen within each member.
- Sequence order is immutable. Existing `experiment-first`/`canonical-first`
  sequences keep their successful-prefix requirements, and legacy v1/v2 and fake
  requests retain their original admission rules. Use a new sequence for the new
  source and ordering mode; historical PASS evidence cannot be moved into it.
- Only one pending attempt is permitted globally. Duplicate completed PASS
  members are rejected. Experiment/drill failures can be retried by a new
  prepare/run attempt, with all prior charges retained. A failed canonical member
  still blocks its entire sequence; `any-order` does not permit selective retries.
- Offline price review derives the remaining set from validated same-sequence
  PASS entries, not a suffix of the chosen starting member. Every remaining member
  needs a quote and maximum. Previous reservations plus all remaining maxima must
  fit USD 200. PASS entries from other sequences cannot reduce that requirement.
- Each run still needs fresh exact-source CI, cleanup/precheck, prices, prepared
  plan and exact approval. The implementation adds no ledger reset or automatic
  refund path. Paid dispatch remains an operator action.

## Separate operator accounting restart — 2026-10-09

After the correction was prepared, the owner explicitly requested clearing the
ledger. All seven prior attempts were terminal; no active Runner, lease or V5.1
instance/disk/firewall remained. The original USD 110 ledger at generation
`1791580114713617` was backed up byte-for-byte under
`.local/v51-ledger-backups/1791580114713617/`, outside Maven output and ignored by
Git. Its SHA-256 is
`710ba869435f13c5fbc540469895d5dd7897340a9416517de66e1f9011b29a4d`.

A write conditional on that exact generation replaced only the current budget
ledger. Read-back confirmed generation `1791584099285775`, no entries, USD 0 / 200
and no active lease. The backup directory retains the original bytes, inspected
plan and PASS receipt. Historical experiment/cleanup/evidence objects were not
deleted. This explicit accounting restart does not refund prior cloud spending
or turn a failed attempt into a successful one.

Fresh plans must use the new ledger observation and a new source-bound sequence.
The USD 200 ceiling and ordinary failed-attempt accounting remain unchanged;
future resets require separate operator authorization.

## Startup/order batch verification (PR #312)

Deterministic startup regressions cover both leader switches, unchanged leader,
convergence, wrong epoch, bounded-leader rejection, original and clipped
deadlines, late replies and transport failure propagation. Ledger regressions
cover all 120 permutations, duplicate/pending/identity/failure/budget rejection,
legacy compatibility and complete remaining-set pricing. Prepare/run qualification
also exercises `canonical-3` first using the offline provider boundary.

Local verification passed: 112 focused tests; final five startup regressions and
25 authority/workflow checks; the complete admission gate's 48 native and 221
preflight/admission tests plus its offline qualifications and review validators;
36 control tests and the control failure matrix; 30 CI scope tests. The generated
workflow matches, all sixteen shell blocks parse, and frozen workload/timing-plan
hashes are unchanged. Logs and a file/hash index are retained in
`target/v51-native-drill-flexible-order/validation-summary.json`.

Those checks qualified the earlier controller/admission correction. PR #312
subsequently passed protected CI, and its paid follow-up is recorded above.
PR #313 subsequently passed protected CI. The new staged-startup correction
requires its own protected acceptance. After that
and fresh cleanup/preflight, create a new source-bound `any-order` sequence,
review its remaining budget and manually prepare/run the selected member.
Existing complete owned failure-drill and three canonical CI gates remain
required. All five native members need complete independent replay, retention
and cleanup on one source for final acceptance.
