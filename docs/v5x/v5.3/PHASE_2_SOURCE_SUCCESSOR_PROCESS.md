# Forced-successor source reclamation after repeated process death

Status: local process qualification **PASS**. Phase 2 remains **OPEN**.

This qualifies the source-retirement correction in
[mixed original-ballot completion](PHASE_2_COVERED_CONTEXT_MIXED.md). Actual public
offline bootstrap creates four EMPTY voters. The minority retains its original
ballot-2 certified entry, installs the higher ballot-3 accepted value in ballot 4,
then forces its exact ballot-4 successor and a complete governing floor. Only
that forced successor permits retirement of the obsolete ballot-3 source.

The test executes all fifteen source-retirement boundaries in both halt and
external SIGKILL modes, including both original-file deletions. Each case opens
three fresh workers: the first dies at the selected boundary; recovery dies again
after journal pruning (or during vote resealing if deletion already completed);
the last worker finishes. Fifteen independent lock probes verify that the first
killed worker still holds the original admitted node lock immediately before death.

The independent reader first replays the complete admitted reference chain. It
derives the exact retirement record, original PROMISE/BASIS/capsule, compacted
journal and deletion list from retained bytes. It binds the original node and
materialization paths, source identity, forced vote and actual ownership
observations. Every first/second/final inventory, force trace, process exit,
handshake and lock probe must agree. A resumed transaction preserves the current
vote, selector and floor; it cannot interpret missing input as an empty vote.

One Java matrix test completes 30 cases / 90 workers, plus fifteen lock probes.
Twenty focused Python tests pass. Normal, optimized and relocated replay agree,
and fifteen specified evidence mutations are rejected for their exact reasons.
The measured image peak is seven; this is not a maximum-byte or power-loss test.
All 707 production classes and both production JARs match the preceding batch.
See the [source/build-bound evidence index](phase2-evidence/source-successor-process.json).

This adds tests and evidence only. The public runtime stays disabled. Hidden
applied-endpoint process recovery, maximal resource/lifetime profiles, complete
cross-view storage and the final S/N mapping remain in the
[closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
