# V5.2 Phase 6AK formal histories over SSH

The [delivered receiver service](PHASE_6_RECEIVER_DELIVERY.md) now admits the exact
frozen M01, M02 and M03 profiles in addition to the existing untimed and M04
profiles. The original controllers, public calls, durations, admission counts,
resource sampling, physical/query/read oracles and negative rules remain intact.
This is loopback qualification with a shared Python checkout, not paid cloud
execution or independent-host acceptance.

## Admission and transport

All 26 formal M01–M03 history names resolve to their unchanged frozen profiles.
Altered windows, deadlines, pending limits, mode/profile combinations, implicit
second generations, additional fault controls and duplicate selections reject.
M02/M03 capsules include their exact measurement options; M01 capsules retain
their default configuration and carry no fault/options file. Every receiver checks
the installed bytes before launching its own service/JVM.

The controller uses the existing pinned persistent SSH stream for original calls.
Lost upload, bootstrap and launch responses are qualified during preparation,
before the original observation window. No injected stream loss, business retry,
additional blocking submit or new offered clock is inserted into a formal window.
Each whole history owns fresh receivers, one immutable package and three original
services/JVMs; collection requires their successful terminal state.

## Large stopped exports

The earlier small lifecycle export allowed 4,096 files and 64 MiB. A retained
complete M01 history already contains 8,426 files and about 67.6 MiB on one voter,
so merely accepting M01 profiles would fail during collection. Formal exports now
use the existing measurement bundle limits: 400,000 files, 4 GiB compressed and
expanded, 256 MiB per member and 64 MiB inventory. These frozen limits are not
increased. Untimed/M04 exports retain their existing small bounds.

The small control response carries inventory count, length, expansion and SHA-256
instead of its entire file list. Before extraction, the controller verifies the
first archive member against that descriptor, checks every path belongs to the
expected voter and rejects circular controller metadata. Original byte hashes,
archive integrity and the combined receiver budget are independently checked.
Chunk transfer remains bounded; no raw evidence is omitted or replaced by a
summary. Retained and relocated validation rechecks the same inventory descriptor.

## Recovery defect exposed by the first real gate

`target/v52-remote-formal/run.PyeTM5/evidence/receipt.json` retains the initial
attempt. M02 passed with 31 original reads, four updates and both physical replay
locations. M03 P=4 failed before its saturation window: one follower published
the setup prefix but never established the required recovery floor within the
unchanged 80-second observer allowance. Cleanup succeeded without leftover owners.

The retained trace shows that follower rejected an older `REJOIN_INSTALL` with
`CAPACITY_EXCEEDED` after a newer acceptance arrived. The sender then offered new
transfers while the unsuccessful original transfer still occupied the receiver.
Those offers rejected with `INTEGRITY_FAILURE` until its lease expired. M03's
longer operation lease made this exceed the existing observation allowance.

`AutomaticRejoin.catchup` now sends one `SNAPSHOT_ABORT` for its own transfer when
that exchange fails. Existing ballot, proposer, transfer identity and expiry
checks still gate the abort. It neither deletes accepted/proven authority nor
records a successful install. An unavailable/fenced abort is suppressed onto the
original exception, which remains the reported failure; there is no cleanup loop
or lease extension. Successful confirmed transfers retain their existing behavior.

Two deterministic regressions fail on the original implementation and pass after
the correction: a rejected stale cut followed immediately by a newer proven cut,
and an unavailable abort preserving the original rejection. The six existing
completion, malformed/lost ACK, changed-cut and fencing tests also pass. Original
failed evidence remains intact; a new source-bound gate is required after rebuild.

The first implementation of that correction still sent the installation payload
with an extra `imageDigest` in `SNAPSHOT_ABORT`. The unchanged closed wire schema
accepts only `transferId` and `response`, so the request failed before sending.
The map-only fixture missed this boundary. The comparison at `run.Nr39QI` retains
the repeated M03 floor failure, with 67 rejected later offers and no transmitted
abort. Both new regressions fail once every fixture request and response traverses
real wire encoding/decoding. The corrected sender now uses the existing exact
abort fields; no wire schema or resource limit changes. Recovery completion,
wire and recovery-exchange tests pass after rebuilding the candidate JAR.

## Ordinary selected-pair coverage

The rebuilt attempt at `target/v52-remote-formal/run.twaZrF/evidence/receipt.json`
completed M02's original workload but failed the general physical replay's legacy
six-frame coverage threshold. Its retained evidence has six proven publications,
four successful updates and one fully transferred selected pair: four basis DATA
send/receive observations. The historical runtime matrix's additional traffic is
not a requirement of an ordinary M01–M03 election.

M01 and M02/M03 now explicitly select the same `selected-quorums` coverage already
used by M04. The inspector still reconstructs every selected descriptor/image,
checks contiguous chunks and digests, and recomputes the selection. It requires
actual selection plus both complete basis transfers; it does not skip authority
validation. The historical matrix keeps its original default. Removing either
selected basis from this retained M02 fails with `selection lacks transferred
basis`. Separate entry tests prevent M01/M02/M03 from reverting to the unrelated
legacy coverage threshold. Portable replay of the retained original is recorded
separately from any later freshly executed source. The retained M02 now passes
complete original/relocated replay and all 15 exact negative cases at each
location, at `target/v52-remote-formal/repaired-m02-replay-result.json`; no business
workload was rerun for that result.

## Local acceptance

```bash
scripts/verify-v52-phase6-remote-formal.sh --skip-build
```

This optional gate runs M02 above/1000, M03 P=4, M03 P=65, candidate explicit-strong
M01 r1 and published V5.1 legacy-strong M01 r1. Each M01 retains the full 60-second
warmup, 120-second measurement and all 1,980 offered calls plus its setup read.
Every history must pass original and relocated independent replay and all frozen
negative cases. Minute heartbeats report the current history and stage. The gate
does not automatically repeat a failed history.

The complete core/replication reactor test attempt executed 998 tests, including
four existing skips. One real-TCP mismatched-generation startup failed before a
leader became ready; the original log and Surefire report remain retained. The
three-test `V51AutomaticRejoinTest` class then passed independently in 56.44
seconds. Post-failure host observations showed substantial memory/I/O pressure,
which is a possible contributor, not an established root cause. This is not
reported as an uninterrupted green reactor attempt. All 476 V5.2 Python tests,
21 CI suite tests, five processor tests and the documentation contract pass.
All five reactor modules then package successfully from the corrected source;
that packaging command skips tests already covered above.

The final rebuilt gate at `run.u16QUK` passes all five complete histories in
3,950.755 seconds. All original and relocated physical/query replay and all 158
negative rejections pass, preserving 3,704 reads and 372 updates. All 15 service/
JVM pairs stop cleanly. Per-history elapsed times include preparation, execution,
collection and replay; they are not workload latency measurements.

| Complete history | Seconds | Reads / updates | Negatives per location |
| --- | ---: | ---: | ---: |
| M02 above/1000 | 72.708 | 31 / 4 | 15 |
| M03 P=4 | 71.750 | 5 / 4 | 16 |
| M03 P=65 | 100.377 | 66 / 4 | 16 |
| Candidate explicit-strong M01 r1 | 2802.773 | 1801 / 180 | 18 |
| Published V5.1 legacy-strong M01 r1 | 902.591 | 1801 / 180 | 14 |

The run binds source `5d183cac51e44ad393fc3583158b3a7e868617be` and checkout
`b3e2cc4e0d6c8299532adaa8949a011088e54c2332d90030002cb0a4da0eae08`.
Its receipt SHA-256 is
`bc0413628fe47e8938e3b462b19bd0509c5188a76da2c5d4ad6e7cb3649fa014`.
All 26 files in the recorded execution index remained unchanged until exit.
Later development continued in an isolated linked worktree; this evidence retains
its original binding and shared-Python local scope. The implementation has 13 new
Python tests covering exact profile/parameter admission, large-export bounds,
foreign/circular inventories and verification before extraction. These lightweight
tests join the existing measurement CI command; the expensive SSH gate remains
an explicit local entry point.

`run.yH7jaj` passed the three M02/M03 histories before its explicit-strong M01
failed measured-window query coverage. The fixed original read target lost
leadership; all 1,980 offered outcomes remain present, including every rejection.
The retained trace observes a 1.225-second leader acceptance force and a
2.592-second follower force around expiry of the existing 1.2-second request
budget. This establishes the observed timing, not the underlying host/storage
cause. The later predeclared one-run pressure comparison instead stopped at the
wire-abort defect above. Neither failure is replaced by a partial passing cohort,
and no business request, leader target, duration or deadline is changed.

## Remaining boundaries

`qualifiedMeasurement=false`, `fullRemoteQualification=false` and `paidCloud=false`
remain explicit. One-host SSH does not establish independent boot/clock identity,
private-host routing, deployed Python-helper identity, complete owned five-member
execution or live provider admission. Those steps, protected exact-master full CI
and fresh cleanup/IAM/provider observations remain required before cloud entry.
The historic successful hosted cohort has its original source; it is not silently
rebound to this runtime correction. No POM, workflow topology, frozen workload or
decoder limit is changed. No workflow or paid experiment is triggered here.
