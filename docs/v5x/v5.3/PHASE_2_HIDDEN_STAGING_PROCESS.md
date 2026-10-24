# Hidden applied-endpoint cleanup after repeated process death

Status: local process qualification **PASS**. Phase 2 remains **OPEN**.

This adds fresh-process qualification to
[hidden applied-endpoint recovery](PHASE_2_HIDDEN_STAGING.md). Three actual
offline-bootstrapped voters produce the original certificate and typed application.
The majority publishes a later RANGE that covers, but does not directly expose,
the lagging voter's applied endpoint. Its original supplemental checkpoint and
two observed ACKs are retained and supplied to each cleanup worker.

All sixteen cleanup boundaries execute under halt and external SIGKILL. Each
case has a second recovery interruption and a final successful reopen/install:
32 cases / 96 fresh workers, plus sixteen live lock probes. The final installed
prefix reaches index 2. The supplemental proof authorizes cleanup only; it is
not added to the selected installation ancestry. Cleanup preserves original
votes/source authority and emits no old application acknowledgement.

The independent reader reconstructs the original majority publications and
supplemental proof. It checks the offered proof bytes, the proof digest in the
retirement authority, all three physical snapshots, replay-before-cleanup order,
exact non-replay force events, external kill handshakes, exits and ownership locks.
The earlier shared trace validator remains in use. Typed replay semantics remain
a Java producer check; Python authenticates the saved image/proof bytes.

One Java matrix test and 21 focused Python tests pass. Normal, optimized and
relocated replay agree; 21 specified evidence mutations are rejected for their
exact reasons. All 707 production classes and both production JARs match the
preceding batch. The old six-profile/eight-interruption evidence is also replayed
unchanged after adding a prepared-reference mode to its reader; it is not a new
execution on the current runtime.

The first new reader attempt failed before negative qualification because a JSON
comparison helper was given binary proof bytes. Its code and error are retained;
the correction uses exact binary comparison and has a direct regression. The
original Java run is retained and was not rerun for that reader correction.
See the [evidence index](phase2-evidence/hidden-staging-process.json).

This batch changes no production code, resource/format limits or workflow. It
does not establish power-loss safety or maximum-byte throughput. Complete
cross-view storage, maximal resource/lifetime profiles and the final S/N mapping
remain in the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
