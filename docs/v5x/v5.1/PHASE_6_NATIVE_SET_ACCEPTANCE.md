# V5.1 Phase 6 native five-member review

**Status:** final offline review and baseline-registration candidate, 2026-10-13.
The five paid members completed successfully. This PR adds their independent raw
archive replay and first baseline record; protected acceptance of this review PR
is still required before closing Phase 6 and entering Phase 7.

## Measured sources and original runs

| Member | Prepared run | Native run, attempt 1 | Measured source |
| --- | --- | --- | --- |
| canonical-1 | 38280005640 | [38280933954](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38280933954) | `f46f9a4` |
| canonical-2 | 38300238047 | [38300809738](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38300809738) | `f46f9a4` |
| canonical-3 | 38345952012 | [38346492463](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38346492463) | `7100b61` |
| experiment | 38362642098 | [38363263163](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38363263163) | `7100b61` |
| failure-drill | 38371664898 | [38372566659](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38372566659) | `7100b61` |

Exact original source: `f46f9a4ea624df2b42902efd0b633c30933ae2f2`, protected by
[CI 38231529564](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38231529564),
attempt 1, all 46 jobs. Corrected source:
`7100b61e752647c52246cc86f2887fefa00821ea`, protected by
[CI 38339508687](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38339508687),
attempt 2, all 46 jobs in that exact attempt. Earlier failed attempts remain historical.
This PR's later commit is the review source, not the measured source.

The [operator-authorized image continuation](PHASE_6_IMAGE_CONTINUATION.md)
permits only these two inherited canonical members from sequence
`eb7859da90c94c468215f2867638b0bf` and the remaining three from
`c4d557b802ec49cd843081326608becb`. Their original identities are retained. The
173-file payload comparison keeps all JARs, adapters, JDK, guest Python and
workload bytes fixed, normalizing only the helper's checked source field and
excluding the separately verified CI build manifest. Future batches still require
their normal common source/sequence. This exception is not general mixing authority.

## Review boundary

The original Actions ZIPs are downloaded through the authenticated artifact API;
their exact byte counts and GitHub SHA-256 digests are pinned before extraction.
Original producing runs, attempts, successful execution/upload steps and sources
are retained beside each archive. No new workload or paid cloud execution occurs.

Each member is independently checked for:

- Closed archive paths and size budgets; complete original binary parts and hashes.
- Historical plan and explicit approval, original Runner/run/request identity,
  selected preset/repetition and exact cell coverage.
- Thirteen actually created numeric resource IDs matched to all cleanup absence
  observations; successful retention and lease release.
- Disjoint original monotonic intervals, elapsed totals and correct soft-budget
  observations. An overrun requires its warning; malformed arithmetic remains a
  failure. Legacy hard-budget evidence retains its original rules.
- Original per-cell timelines and raw evidence, replayed by the existing independent
  canonical, fault or experiment validator. Recomputed aggregates must equal the
  original cloud aggregates exactly, including negative evidence checks.
- Immutable GCS completion/evidence/inventory hashes, every retained metadata and
  workload part, terminal ledger completion and the absence of an active lease or
  unresolved reservation in the collected control snapshot.

All five inputs are mandatory. A green summary, duplicate/missing member, wrong
repetition/source, corrupt part, changed retained completion or failed raw replay
cannot produce a set baseline. The registry command has no overwrite option and
writes only after every raw replay and set check succeeds. The separate `check`
command verifies compact review/registry integrity; it does not replay raw evidence.

The raw validators preserve their component-level `fullRemoteQualification=false`.
Only the final five-member review reports complete remote qualification. Protected
acceptance of this PR and Phase 6 closure remain a separate repository decision.

## Independently replayed results

The [complete compact review](phase6-cloud-review.json),
[original artifact/GCS provenance pins](phase6-cloud-provenance.json) and
[first baseline registry](cloud-benchmark-baselines.json) are checked in together.
The canonical review SHA-256 is
`c0cf273dc68813bc056598c7f9c678bd39d28b16e6dd794acda85b8a653c47a2`.
All five recomputed aggregates equal the original cloud aggregates exactly.

| Member | Cell instances | Rich calls, including warmup | Measured rich calls | Fault calls | Evidence negatives | Original Actions run duration |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| canonical-1 | 15 | 1080 | 1020 | 103 | 169 | 2h47m14s |
| canonical-2 | 15 | 1080 | 1020 | 103 | 169 | 2h40m09s |
| canonical-3 | 15 | 1080 | 1020 | 103 | 169 | 2h46m54s |
| experiment | 4 | 270 | 240 | 26 | 42 | 1h06m43s |
| failure-drill | 12 | — | — | 103 | 129 | 1h41m32s |
| **Total** | **61** | **3510** | **3300** | **438** | **678** | — |

These are scenario instances across repetitions, not 61 different scenarios.
Canonical healthy has 240 measured calls per mode, 24 samples per operation
across four ABBA windows. The compact review retains each operation/window's
sample count and nearest-rank p50/p95/p99 separately for JVM API latency and
guest-driver round trip. Each healthy operation/window has only six samples;
those tail percentiles are diagnostic. Read-heavy and sustained retain their
120 and 180 measured calls. Fault histories remain separate from latency samples.

The following summaries use only healthy measured API intervals; each B/A is
the equal-count instrumented mean divided by baseline mean across all operations.
The machine review also retains B/A separately for every operation.

| Mode | Canonical 1 B/A | Canonical 2 B/A | Canonical 3 B/A | Maximum sampled member RSS, MiB, by repetition |
| --- | ---: | ---: | ---: | --- |
| Published V4.4 local | 0.975 | 1.009 | 1.005 | 113.2 / 111.9 / 113.4 |
| Published V5.0 configured | 0.974 | 0.974 | 0.979 | 123.5 / 124.7 / 126.4 |
| Candidate V5.1 automatic | 0.941 | 0.975 | 0.973 | 174.3 / 166.1 / 169.5 |

Sub-unit B/A observations do not prove instrumentation improves performance.
No timing warning was recorded by these five original soft-budget completions.
Their per-stage seconds remain in the review, including canonical preparation
at 2699–2829 seconds and validation/retention at 1574–1889 seconds. Actions run
durations above include workflow setup/upload and are not measurement windows.

## Accounting, scope and remaining work

All five selected members reserved USD 25 each. The current ledger records
**USD 250 cumulative reservations**, including historical attempts; this is not
an observed provider bill. No refund, reset, migrated ledger entry or discarded
failure is part of this review. Time and cost thresholds are advisory under the
accepted [soft-budget policy](PHASE_6_NATIVE_SOFT_BUDGETS.md); fast failure,
original ownership and the GitHub platform lifetime remain unchanged.

Each original completion records all thirteen resources absent. The final control
snapshot has no active lease and no PENDING reservation. These are authenticated
historical observations, not a fresh IAM/quota/cleanup admission for another run.
Raw archives and GCS evidence retain their original retention policy and identities.

This corpus tests protocol/per-operation behavior at the frozen offered load.
It does not establish production-scale throughput, a general p99/failover SLA,
public follower reads, membership changes or mixed-version upgrades. Resource
peaks are sampled observations. Per-operation API timings and guest-driver round
trips use their own clocks; controller window-command duration includes whole
window execution and is not treated as API latency. ABBA ratios describe observed
instrumentation cost without a new speedup target.

After this review PR passes protected CI and is merged, reconcile its commit/run
and close Phase 6. Begin Phase 7 with a separate release-candidate entry:
compatibility consumers, API/Javadoc review, canonical artifacts and reproducible
builds, release notes and publication checks. No version bump or release is part
of this batch.

## Reproduction

Use Python 3.11 and Java 21. Retain the pinned published controls in
`target/v51-published-controls`; backup checks execute the independent V4.4 restore.
The input directory has one subdirectory per member, each containing authenticated
`run.json`, `jobs.json`, `artifacts.json` and the original `experiment.zip`.
Also retain the three authenticated corrected-source preparation directories and
the generation-pinned five-member continuation observation snapshot. See the
[continuation procedure](PHASE_6_IMAGE_CONTINUATION.md#operator-procedure-after-merge)
for original package provenance; the commands below do not fetch or authenticate
new GitHub/GCS observations themselves.
The provenance JSON records the artifact IDs, ZIP lengths/digests, original API
metadata hashes, GCS object paths/generations and ledger generation. Retain the
authenticated observation snapshot alongside these raw inputs; the compact
repository JSON files alone cannot reproduce raw qualification.

```bash
python3.11 -m scripts.v51.native_set_review review INPUT_DIRECTORY \
  --output FRESH_REPLAY_DIRECTORY \
  --source 7100b61e752647c52246cc86f2887fefa00821ea \
  --observations CONTINUATION_OBSERVATIONS_JSON \
  --prepared canonical-3=ORIGINAL_CANONICAL_3_PREPARATION \
  --prepared experiment=ORIGINAL_EXPERIMENT_PREPARATION \
  --prepared failure-drill=ORIGINAL_DRILL_PREPARATION \
  --workers 3 --registry NEW_REGISTRY_JSON
```

This is a one-time frozen-continuation review entry. Existing outputs and registry
files are never overwritten. Input paths may relocate; original embedded authority
paths and measured identities remain unchanged. Up to three whole-member replays
may run concurrently; every member and original measurement window is preserved.

```bash
python3.11 -m scripts.v51.native_set_review check \
  --review docs/v5x/v5.1/phase6-cloud-review.json \
  --registry docs/v5x/v5.1/cloud-benchmark-baselines.json
```

## Local validation

- Complete five-member raw replay, including independent physical/history/read,
  restore and negative-evidence validation; original aggregates matched exactly.
- The CI Python `core` lane passed all 1250 tests with no skips. Two subsequently
  added registry/provenance regressions also passed; the final targeted review,
  continuation and legacy archive suites passed 31 tests.
- All 36 CI classifier/Python partition tests passed. The documentation contract,
  changed local links and whitespace checks passed.
- Restricted local execution initially rejected an unchanged writable-parent
  fixture; the same module passed all 19 tests with normal host permissions, then
  the complete core lane passed. No ownership guard was weakened.

Local receipts, failed tool-development attempts and verified original downloads:
`target/v51-phase6-final-review/`. Repository summaries retain only review data and
original artifact/record hashes; large raw archives remain outside Git.
