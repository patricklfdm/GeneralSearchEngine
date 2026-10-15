# V5.2 Phase 3: public replica reads

**Status:** 3A locally verified; 3B external three-process
qualification and protected acceptance remain pending. Follow the
[local commit sequence](LOCAL_DEVELOPMENT_SEQUENCE.md). No cloud run is authorized.

## Public admission and ownership

The GSE automatic handle now overrides `read(options, callback)`. Nulls fail
synchronously. Other rejected calls return a failed Future without invoking the
callback. A stopped handle returns NOT_READY; third-party implementations retaining
the interface default still return UnsupportedOperationException without side effects.

All policies share the original P admission slots and the
[Phase 2](PHASE_2_CAPTURE_KERNEL.md) R=min(64,P-1) limit. Local progress waits do
not enter the ordered writer queue. A strong request queues one fresh NO_OP in
that existing queue, then gives the completed epoch/index barrier to application
capture. The ordered turn remains owned until capture or rejection, so a later
write cannot replace the barrier cut first. A private bounded latch releases that
turn before the callback or user completion handlers finish; it does not extend
the invocation deadline. It never downgrades to a local read. Client timeout/cancellation does not
pretend an outstanding NO_OP has stopped: its permit remains accounted until the
original runtime operation settles. No mutation or callback is retried.

One deadline starts at invocation. Positive minimum waits use the smaller of the
requested wait and configured operation timeout; zero wait is one scheduled
capture attempt under the ordinary operation timeout. Admission, queueing and
capture share that deadline. An active cooperative callback may finish later.
Close rejects uncaptured work before stopping timers/ordered work, and retains
the underlying view until active work releases it. Same-handle reentry uses the
existing context guard; pure metadata and cached status remain available.

## Follower publication: required source-level addition

The first public follower test failed with DEADLINE_EXCEEDED. Inspection showed
that V5.1 followers persisted proofs and recovery snapshots but did not publish
their application continuously: publication was coupled to leader commit/activation.
Increasing a wait or rerunning could not provide the missing application path.
The original failure is retained in `target/v52-public-read/public-tests-2.log`.

Attaching the V5.2 read queue now enables a local publication continuation in the
existing automatic protocol/application pipeline. A quiescent follower with a
new verified proven prefix reconstructs through the existing single staged
application and publishes it on the same application worker. It creates no vote,
leader activation, application mutation, client-write acknowledgement or authority
record. It does not allocate a reconstruction per reader. The local action reuses
the existing reconstruction/publication bounds; it cannot overlap another such
action. The new `Publish.local` flag is internal, not a wire/storage field.

Snapshot installation reports RECOVERING to readers until that installed prefix
is materialized. Ordinary incremental publication can continue to expose the
previous committed prefix while preparing its successor. A higher promise does
not invalidate an already verified local prefix or turn its publication into
leadership. Strong reads still validate their fresh activated epoch.

Local publication uses distinct BEFORE_LOCAL_PUBLISH / LOCAL_PUBLISHED observer
events, preserving the existing leader publication event contract. Two inherited
read-only Java probes now observe the bounded worker's ordinary queue plus read
marker while preserving their historical ThreadPoolExecutor handling. These are
qualification observers, not alternate authority or caller-accessible read paths.

## Validation boundary

The follower correction passes three deterministic real-store protocol cases,
six initial public policy/query/lifetime cases and all 21 original protocol tests.
Accepted-only entries cannot publish; proof progress alone does not complete an
application publication; an installed snapshot remains non-readable until its
publication; a higher promise cannot activate leadership through local publication.

Additional public checks cover P=1 legacy maintenance, queued-write ordering and
cancellation during cooperative close. The initial new public test also
had a test-only accessor compilation typo; its log remains retained. The next
capture-order run exposed a legitimate NOT_READY transition when an uncaptured
follower waiter entered snapshot recovery. The healthy carried-token test now
waits for the follower publication before issuing its single read; it does not
retry that read. State-transition rejection remains covered by separate queue and
real-store cases. Both original failing logs remain retained.

These tests exercise actual public handles and real sockets in one JVM. They are
not the required external three-JVM physical/history oracle. Phase 3B must retain
that evidence and compare all seven query results with published V4.4. Full
S01–S30 fault coverage, combined hardening, frozen measurements and cloud admission
remain later work. No hosted or paid acceptance is implied by local test success.

## Local verification record

- Complete reactor before the final capture-order correction: **964 tests**, four
  existing skips, zero failures/errors; `target/v52-public-read/reactor-package.log`.
- The capture-order run passed all 21 inherited protocol and 14 inherited public
  runtime tests, but exposed the healthy-fixture recovery race described above.
  After correcting that fixture, all **26** affected V5.2 queue/public/publication
  tests passed and current JARs were packaged (`capture-order-tests-2.log`).
- All seven external consumer modules passed (24 tests in the six test-bearing
  modules, plus the V1 source-only consumer); `target/v52-public-read/consumers.log`.
- Updated foundation passed at `target/v52-foundation/run.l0ykpD/evidence`: fixed
  token/API checks, published V5.1 binary compatibility, all 950,492 finite-model
  states / 3,934,700 transitions and all 16 synthetic rejection families. These
  remain foundation checks, not physical runtime acceptance.
- Original backpressure gate passed both internal mailbox cases and all four
  public cases, with retained evidence/negative replay at
  `target/v51-backpressure/run.WcXNv4`.
- Original three-mode performance gate passed all 270 healthy calls, nine
  SIGKILL/rejoin calls, 30 evidence negatives and owned-process cleanup at
  `target/v51-performance/run.ROuMpG/evidence`. The historical mode label remains
  `candidate-v5.1-automatic`; the receipt hashes the actual 5.2.0-SNAPSHOT JARs.
- The V5.1 documentation contract, 723 changed-document local targets and
  whitespace checks passed. Local Java was Ubuntu OpenJDK 21.0.12.1, not the
  hosted Temurin toolchain. No protected/hosted acceptance is claimed.

Receipt/log hashes and the local changes list are retained in
`target/v52-public-read/validation-summary.json` and `changed-files.txt`.
