# V5.2 Phase 6U bounded verified trace replay

**Status:** replay optimization locally qualified. The first formal
cohort was interrupted during independent replay, with its complete first history
retained. It is not an accepted cohort. A new implementation/machine freeze and
fresh complete cohort remain required before local measurement acceptance.

## Observation, preserved failure and scope

Implementation `7c6b9e1` passed the complete reactor: 997 tests, four existing skips,
zero failures/errors. Build-bundle creation initially rejected retained JAR mtimes.
The old JARs were preserved and genuinely regenerated; the already successful
exact-source test reports were retained. No timestamps were fabricated and no
tests were silently replaced by skipped results. The second bundle creation passed.

Machine-only freeze `ee9bdb9` preceded the first formal run. The published V5.1
repetition completed its unchanged 60/120-second windows and all three JVMs closed
cleanly. During the 120-second measured window, all 120 updates succeeded; reads
had 347 successes and 853 consumer-executor rejections before API invocation.
All 1,200 original read results remain in the ledger. Queue rejections were already
declared outcomes; these observations do not justify changing rate, queue capacity
or acceptance. They are not general engine throughput or consistency-equivalent
speedup claims.

At 765.342 seconds the agent explicitly interrupted the cohort's independent
replay to investigate repeated decoding. No measured JVM was running at that point.
The receipt records `KeyboardInterrupt`, zero fully qualified members and the
original stopped history at `target/v52-formal-measurement/cohort-1/`. The remaining
27 histories did not start. This is an agent-aborted validation attempt, not an
observed runtime correctness failure or a successful formal measurement set.

## Verified bytes once, semantic checks on every pass

Profiling one complete positive validation of that retained history showed about
2.67 million filesystem-stat calls and 1.12 million file opens. Every semantic
pass reconstructed the same observation chunks, rechecked their hashes and parsed
both envelopes and records. The profiled positive validation took 97.7 seconds.

`measurement_verified.py` first runs the unchanged strict lossless decoder over
every original row, including all row/chunk/count/byte/generation bounds. It writes
exact verified UTF-8 bytes into private anonymous temporary files, with per-row
lengths and hashes. Later iterations read bounded rows using independent offsets,
verify their hashes and return fresh decoded objects. Nested iterators and negative
views cannot alter another pass. No complete history is buffered in memory, and
no pickle or executable serialization is accepted.

Each voter's spool is bounded by the existing 8-GiB decoded-byte ceiling plus
36 bytes for each of at most 262,144 rows. This temporary representation is not
authority or retained source evidence. The original full inventory is checked
before and after the replay session, and complete spool hashes are checked before
cleanup even if a semantic pass stops early. Failed original decoding never
exposes a partially verified trace. The spool is removed on success or failure.

M01, M02/M03 and M04 still execute all physical, publication, history, captured-cut,
query and resource checks for every positive/negative pass. The original must pass
before any negative can count. Exact negative case/status/reason equality and
original/relocated result equality remain required. Success files are written only
after final integrity checks. The short CI consumer's existing entry is unchanged.

The same complete positive result is exactly equal with verified replay. Its
profiled elapsed time was 63.0 seconds, including spool creation and final integrity
checks. Profiling adds overhead; these two executions demonstrate validator cost,
not a product performance gain or a guaranteed full-cohort duration.

## New freeze after an interrupted cohort

The machine entry now permits replacing an older tracked freeze on a clean
committed implementation. It preserves the old plan in the new storage directory;
the original history and original Git freeze commit remain untouched. The new
freeze must again be the sole changed file in a direct child commit. Admission
reconstructs the implementation parent's complete Git inventory, including any
previous freeze file, and rejects a forged implementation fingerprint.

This permits a new cohort after a reviewed implementation correction, without
resuming the old run or splicing prior members. Workload parameters, request counts,
semantic deadlines, runtime JAR logic, control pins and correctness requirements
are unchanged. The new plan records the temporary spool bound explicitly.

## Validation record

Receipts, profiles, original failed attempt and replay comparisons are retained
under `target/v52-replay-efficiency/` and the original cohort directory. Seven new
tests cover exact repeated/nested iteration, mutation isolation, original decoder
bounds, duplicate JSON, spool corruption/truncation/forged hashes, original evidence
changes after preparation, and cleanup on semantic failure. Real temporary Git
tests also cover replacing an earlier freeze without losing its parent identity.

The complete V5.2 Python suite passes 218 tests. Complete original/relocated replay
of the retained M01 history passed with 28 exact negative rejections in 607.924
seconds. All thirteen prior M02–M04 complete relocated replays, including their
190 exact negative results, matched the original validator's results exactly
(72.221 seconds). The portable M01 replay and smaller retained comparisons partly
overlapped; these are observed verification durations, not isolated benchmarks.
Documentation/CI inventory, changed local links, shell syntax and whitespace checks
passed. Receipts and SHA-256 indexes are in the validation summary at the directory
above. None of these retained-data checks reruns a business workload or promotes
the interrupted cohort to full acceptance.
