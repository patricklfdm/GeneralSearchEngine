# V5.2 Phase 4 schedule-to-evidence map

This map preserves the enumerated requirements in
[TESTING_AND_EVIDENCE](TESTING_AND_EVIDENCE.md). It separates deterministic tests,
real public handles in one JVM, and independent three-JVM physical evidence.
It is a local implementation/validation map, not protected hosted acceptance.
Final local revalidation is recorded in [Phase 4 qualification](PHASE_4_QUALIFICATION.md).

Java test names below refer to the
[replication test package](../../../general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication).
The public process drivers and independent validators are in
[scripts/v52](../../../scripts/v52). Each process receipt retains its original
source/tree/build/run/attempt, physical authority and published V4.4 query replay.
Different histories and revisions are not relabelled as one exact-source run.

| Schedule | Implemented variants and concrete evidence |
| --- | --- |
| S01 | Seven independent [consumer modules](../../../compatibility/pom.xml), including actual V1 execution added in 4D11. `V51PublicRuntimeTest.completeFacadeUsesOneEntryPerCallAndNoOpKeepsPageCursor` exercises inherited read/mutation/maintenance calls and rejects follower legacy reads. Existing V5.0 public contract/lifecycle/runtime tests retain configured semantics; their gates remain required. |
| S02 | `foundation.py` compiles the old implementation against published V5.1 and executes it with candidate JARs; default explicit reads reject UnsupportedOperationException. `V52PublicReadTest.stoppedAndClosedAdmissionRejectsPromptlyWithoutInvokingCallbackOrCreatingFiles` covers stopped/closed handles and no created files. |
| S03 | `public_reads_harness.py` and `public_read_application_harness.py`: all seven methods, three policies, absent documents, ranking/highlight/explanation and repeated multi-query reports. Independent actual-prefix and V4.4 replay binds returned policy/token/index/sequence. |
| S04 | 4B `isolated-follower`: observe actual selected pair, isolate its other voter, commit on the majority and prove the isolated stale prefix remains older. |
| S05 | `V52PublicReadAuthorityTest.forcedAcceptanceWithoutProofCannotSatisfyEitherLocalPolicy`: actual forced ACCEPT_ACK held before leader processing; stale/covered minimum at k, zero/positive minimum k+1 rejection, then proof/publication and successful new minimum. `V52FollowerPublicationTest` independently exercises the internal store/protocol edge. |
| S06 | 4B `unpublished-proof`: forced proof or verified snapshot, actual held local publication, no fabricated capture at the future index, then released publication/new minimum. Snapshot recovery legitimately returns NOT_READY instead of waiting; this branch is explicitly witnessed. |
| S07 | Three-JVM published-V4.4 imported base sequence 4 at genesis index 0, followed by actual control-only activation/strong NO_OP. `public_reads_evidence.prefix` independently separates log index from application sequence. |
| S08 | `V52PublicReadAuthorityTest.confirmedBulkThenStrongTokenWaitsForTheLaggingFollowersActualPublication`: public bulk completion precedes token issuance; selected follower keeps an older captured view, registers a behind minimum with observed waiter/timer ownership, then publishes and returns the whole bulk. Snapshot fallback is held separately so this tests ordinary proof publication, not the S20 recovery gate. |
| S09 | `V52ReadLifecycleTest.allZeroAndPositiveBoundRelationsUseTheActualCutWithoutExtraWork` enumerates below/equal/above at zero wait. Public identity/fault/authority cases exercise covered and ahead bounds; no fresh barrier is attributed to a local policy. |
| S10 | The same deterministic relation matrix includes positive waits and absent-progress expiry. S08 supplies actual waiting/publication success. The 4D10 public negative fixture retains a genuine positive-wait deadline failure with no callback. |
| S11 | `V52PublicReadTest.queuedWritesDoNotOvertakeFreshStrongCapture` checks interleaved token/write submission. 4D1 pauses a real token-producing callback while later updates/deletes are queued and verifies its old cut and later state. N11 rejects forged confirmation edges using both controller sequencing and originating-worker response order. |
| S12 | `V52ReadQueueTest.registrationRechecksPublicationAndDoesNotLoseEitherWakeupOrder` plus the exact-deadline tests in that class and `V52ReadLifecycleTest`: publication before/during registration, subsequent wakeup, exact deadline and late timer delivery. Terminal results never revive. |
| S13 | 4D2 public identity cases cover group/history/manifest mismatches at equal numeric index with valid checksums; 4D3 new-group import preserves application sequence. Deterministic P=1 mismatch tests enforce identity-before-capacity. |
| S14 | 4B capture/release halt and SIGKILL cases retain pre-reopen files, lost responses and actual process generations. A successor and retained-disk restarted follower use the original token successfully. |
| S15 | 4D4 `token-below-floor`: two complete source packets, actual floor advancement, old-generation deletion and empty retired journals; follower snapshot install plus carried old minimum at the new cut. |
| S16 | 4D3 actual public backup/export and verified new-group bootstrap; sequence preserved and group/history/manifest changed. Old token rejects, fresh token works. A token-only empty authority directory cannot start or recreate missing disk history. |
| S17 | 4D9 isolated-old-leader variants: fresh strong requires a quorum and fails; stale/covered minimum retain the valid old cut, ahead minimum rejects. Heartbeat loss alone is not treated as evidence that the status enum has changed. |
| S18 | 4C2 `promise-before` rejects strong capture; `promise-after` allows an already captured cut. Release halt/SIGKILL variants retain lost responses, copied authority and restarted compatible reads. |
| S19 | 4D9 both local policies with real higher PREPARE before/after capture; CANDIDATE and actual installed-snapshot RECOVERING transitions reject queued/new captures while preserving already captured callbacks. No status-only or synthetic permission grants. |
| S20 | 4C2 install pause rejects non-readable state, followed by actual publication and successful new minimum; install rejection halt/SIGKILL variants retain complete process/authority edges. 4D9 also verifies old-callback overlap with actual recovery. |
| S21 | 4D1 repeats a seven-method report in the same callback while update/updateAll/remove/removeAll/index create/drop/add queue; all three policies preserve one generation. Later physical publications and query truth are independently checked. |
| S22 | Foundation compile-negative page/mutation calls; `V52PublicCursorTest` covers original first/next paging, NO_OP continuity, changed automatic materialization, successor and reopened handles. Cursors are actual opaque objects retained between handles in one JVM, not an invented serialized cursor format. Nested legacy paging rejects. |
| S23 | 4D5 P=4 real three-JVM saturation: R=3 behind waiters, excess explicit rejection, reserved writer progress and complete post-run ownership/permit/timer release. |
| S24 | 4D6 P=1 rejects all three explicit policies without allocation while legacy writes/reads continue. 4D5 P=65 and default pending limit P=10000 both admit at most 64 explicit reads. Other fixture bounds remain declared small qualification bounds, not all production defaults. |
| S25 | Eleven 4C1 schedules cover original-Future queued/waiting/pre-capture/captured/completion cancellation, plus halt/SIGKILL at release. Atomic ownership and actual completion return determine release; Future completion alone does not. |
| S26 | 4C1 waiting close and paused captured close, incomplete first close and completed second close; halt/SIGKILL while held. Public/kernel tests separately prove retained store ownership during incomplete close. |
| S27 | `V52ApplicationReadCutTest` and `V52PublicReadTest`: original Throwable/null preserved and wrapper released. `V52ReadQueueTest`/`V52ReadLifecycleTest` plus 4C1 hold callbacks and completion handlers, retaining permits until actual return. API deadlines do not promise interruption of an already running callback. |
| S28 | `V52ReadQueueTest.anOlderUnsatisfiedMinimumDoesNotBlockEligibleFifo`; `V52ApplicationWorkerTest` verifies coalescing, ordinary capacity and 16 replenished read/publication turns with both queues nonempty. Timers expire while another public callback is held. Finite controlled fairness coverage is not an unbounded liveness proof. |
| S29 | `V52ApplicationReadCutTest` rejects all seven methods after release/from another thread. Public tests retain the wrapper in a closure/result, reject same-handle query/mutation/backup/checkpoint/start/close reentry and preserve metadata/status/cached diagnostics. |
| S30 | 4D8 corrupt manifest/genesis startup and fatal authority-I/O tests; queued/new reads reject while a valid already captured view can finish. 4D2 malformed/version/reserved/trailing/checksum vectors, Long.MAX_VALUE and max wait; no allocation scales with the numeric bound. This does not claim per-read scanning for arbitrary external filesystem tampering. |

## Independent negatives and process boundary

The 4D10 gate covers N01–N16 with 28 targeted physical/history mutations, exact
rejection reasons, valid originals first, and identical results after packaging
and relocation. The Phase 1 model and its synthetic mutations remain separate.
Mandatory process-death families S14/S18/S20/S25/S26 each have real public JVM
halt and controller SIGKILL evidence; surviving/retained histories are not rebuilt
from client tokens or invented successful responses.

## Remaining phases and acceptance

Phase 5 combines independent faults with retained read ownership. Phase 6 must
freeze M01–M04 before measurements, retain all outcomes and prepare the fresh
five-member cloud qualification. Neither phase is completed by this map. The local
commit sequence continues without pushes; final protected exact-source full CI,
master merge and fresh manual cloud admission remain required later.
