# PR5: reuse format-schema parsing during independent replay

Implementation base: `d12d682e2a16eb2c9a96b326f2875e97768ddd7f` (PR #326).
This batch follows the [PR4 scope review](CI_CORE_POLICY_REVIEW.md) while keeping
full/docs selection, every suite and all three complete canonical repetitions.
New-source hosted live acceptance passed after PR #327 merged as
`c62e4719f8fd346e0f8997f0800e8fbd69414cbf`; see
[the final report](CI_REFACTOR_ACCEPTANCE.md) for source/attempt identities.
The operator subsequently added [PR6 documentation and integration checks](CI_REFACTOR_HANDOFF.md)
to the same branch; that addition does not alter this replay optimization.

## Measured hotspot, not a new sharding plan

Read-only job/step metadata and full logs were collected for six successful
canonical jobs in two runs, producing attempt 1 in both:

| Run | Tested source | Repetitions / qualification seconds |
| --- | --- | --- |
| [PR 38516949749](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38516949749) | `045a8af4984e003ff0ab5891e034689c93c82c41` | 1: 2803; 2: 2559; 3: 2657 |
| [master 38522705456](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38522705456/attempts/1) | `563dfe290326945d9cf0cda2b556b609d3be85a7` | 1: 2777; 2: 2480; 3: 2254 |

Master's first **workflow** attempt failed in full-size runtime; the canonical
jobs all succeeded and were reused in attempt 2. The six samples are not six
independent PRs or evidence of a population P95. Source changes through the
review base leave the measured qualifiers unchanged. See the
[acceptance record](CI_SHADOW_ACCEPTANCE.md) for all attempts and original failure.

| Part of the qualification step | Minimum / median / maximum seconds across six jobs | Clock / interpretation |
| --- | ---: | --- |
| Initial setup and service/bootstrap preparation | 172.03 / 220.48 / 248.84 | Log timestamp envelope; includes package verification and controller setup. |
| Healthy, read-heavy, sustained cells | 1166.99 / 1186.92 / 1197.27 | Sum of original monotonic cell timers; includes **1080 frozen measurement seconds**, control calls and close barriers. |
| Twelve fault cells | 453.45 / 506.09 / 547.79 | Sum of original monotonic cell timers; includes fault execution and recovery. |
| Collection and service stop | 107.05 / 136.53 / 152.94 | Log envelope; shutdown is not separately timed. |
| Independent aggregate replay | 349.40 / 548.09 / 648.81 | Log envelope including logical/physical validation and negatives. |
| Remaining retention, cleanup and exit | 5.07 / 7.31 / 8.00 | Residual log envelope; not an isolated pack benchmark. |

Separate job steps build the guest package in 12–19 seconds and upload final
evidence in 40–67 seconds. Dependency-ready-to-start delay is 2–3 seconds.
Runner waiting, job execution, billed money and operator rerun delay are distinct.
Log ingestion sometimes batches adjacent records; near-zero individual fault
replay intervals are not exact CPU timings. No negative-test-only timing can be
derived from these logs. Raw events and interval definitions are retained.

Replay is a demonstrated variable cost. Existing joint replay reuse is already
implemented in `guest_canonical_evidence`; this batch does not remove another
replay, any negative case, any raw trace or any validation. Complete histories
retain their one request/source/lease, seventeen fresh groups, sequential cells,
1080 calls and combined stored/decoded evidence budgets.

## One optimization and its equivalence boundary

[format_inspector.py](../scripts/v51/format_inspector.py) previously reparsed the
25 KB format catalog for every nested record/context check, and reparsed and
merged two wire extension catalogs for each packet. A ten-pass frozen-fixture
profile observed 1290 public `load()` calls and 2680 JSON decodes. After schema
reuse it observed 1014 JSON decodes, with the same 1670 file reads. Fixture CPU
profiling is mechanism evidence, not a full CI speedup measurement.

Three private, size-one caches retain only parsed storage, bootstrap and merged
wire **schemas**, keyed by all current input bytes. Every use still reads its
catalog files. Deletion, corruption and same-size/same-mtime changes remain
observable. There is no path/mtime-only cache, stored PASS reuse, cached authority,
decoded frame, decoded trace, proof, history or evidence inventory.

Cached trees do not escape and are never modified after construction. The
public `load()` still returns a fresh mutable object; decoded record/packet
results also remain independent. Wire extensions are merged into a private
construction, so repeated validation cannot accumulate enum members or alter
the storage schema. Each cache holds only its latest input, rather than every
catalog seen in a process. Catalog JSON parsing failures are not cached.

The full record/packet validation sequence remains: capacity, version/kind,
digest, canonical body, exact schema, semantic fields, nested contexts and
membership/ballot/wire correlations. All budgets and frozen file bytes remain
unchanged. The shared inspector can be used by offline and native evidence
readers; no paid workflow, pricing, lease or runtime parameter is changed.

## Validation and retained failures

One complete sequential before/after replay pair passed on identical retained
input using Python 3.11.15 on Linux/WSL2:

| Inspector | Complete replay seconds | Outcome |
| --- | ---: | --- |
| Original uncached parser | 361.929 | PASS |
| Current content-keyed schema reuse | 143.271 | PASS |

The entire decoded result is exactly equal, including all 15 cells, 1080 rich
calls, component physical/history results, negative case/status/reason lists,
source/request identities and stored/decoded evidence budgets. All 2291 raw
files (225,531,244 bytes) still match the original extraction inventory after
both executions. Only replay outputs were written to separate directories.

This pair saved 218.658 seconds (60.41%) **in local replay**. One sequential pair
with uncontrolled host load and OS caches is not a hosted CI speedup estimate,
population statistic or billing measurement. Workload durations were not
remeasured or shortened in this local pair. The subsequent full live hosted
acceptance is recorded below.

- Five new regression tests cover warmed caches with missing/corrupt catalogs,
  same-size/same-mtime changed contents across all four source files, public
  object independence, malformed evidence after a valid call and parsing reuse
  while files remain reread. They are in the existing `test_format` module and
  remain part of the exhaustive Python core partition.
- Differential execution against the original inspector compares **312 exact
  outcomes**: 52 positive frozen record/wire vectors plus five corruptions of
  each, including unchanged rejection type/reason. No fixture is regenerated.
- Existing storage/history/physical and canonical coordinator negatives remain
  selected. The shared-build version test now explicitly covers simultaneous
  final and SNAPSHOT candidate pairs, exact POM selection, mixed/extra/wrong
  roles and mismatched Manifest versions. PR #322's exact-source receipt,
  nine-JAR/three-POM, six-consumer and 90-day contracts remain intact.
- Initial local tests were rejected by the sandbox's `nobody` ancestor ownership
  mapping (`delivery writable parent`). The same 89 tests passed under normal
  host filesystem ownership; both logs are retained. No receiver check changed.
- An initial replay of historical run `37869232192` reached a missing bounded
  startup observation required by today's validator. That old archive cannot
  establish current complete acceptance. Its failed log is retained; the
  validator was not relaxed and the old evidence was not rewritten.
- The current comparison instead uses master run `38522705456`, repetition 1,
  job `115717599763`, artifact `11876512977`. Downloaded ZIP SHA256 is
  `930e5b7400f10d1a12f0bef919682634f0599ae5342312411b411ebcf9f1dd44`, matching
  GitHub's artifact digest. Extraction checks paths/types/size/CRC and binds the
  original receipt to its source and repetition. Replay outputs are separate
  from immutable raw input.

Focused test groups passed: 115 format/storage/history/rich tests, 89 physical/
canonical/release/partition tests, 19 release/version tests after adding the
coexistence case, and 85 CI/Required/shadow/preflight tests. These groups overlap
and must not be summed as unique tests. Documentation contracts, suite registry,
changed local links and whitespace also passed. No Maven clean/build or full
live local workload was run for this optimization.

Raw GET results/logs, artifact/ZIP/extraction inventory, review scripts, profiles,
original implementation, tests and replay receipts are retained under
`target/ci-canonical-hotspot/`. Original PR0 and earlier failure evidence remain
intact. The log CLI initially refused terminal escape sequences; its error logs
are retained and the successful GET stores those original bytes in files.
`replay-comparison.json` binds both implementation hashes, original artifact,
raw inventory, complete result equality, timings and environment;
`validation-summary.json` indexes the combined batch's checks and limits.

## Hosted acceptance and rollback

This batch changed an oracle implementation, so **normal full PR and exact-master
CI were required**. [PR run 38540436241 attempt 2](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38540436241/attempts/2)
and [master run 38548426916 attempt 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/38548426916/attempts/1)
each freshly executed all 46 jobs successfully, including three complete live
canonical repetitions, component tapes, rich aggregate, negatives and release
fixtures. The PR tested merge and final master have identical trees. The first
PR attempt's nineteen platform-error cancellations remain separately retained.

Six completed canonical jobs show independent replay at **138.18–271.86 seconds,
median 235.60**, compared with the earlier six-job median 548.09. Complete-workflow
Required spans were 48:14 for the successful PR attempt and 48:37 for master.
The [acceptance report](CI_REFACTOR_ACCEPTANCE.md) separates preparation, rich/fault
cell timers, collection, replay, dependency waits, execution totals and failed
attempt costs. These are measured observations, not a controlled end-to-end
benchmark, billing result or population P95. Hosted log ingestion may batch lines.

PR5 acceptance and PR6 reconciliation are complete; core activation remains
deferred. The observation read logs, metadata and small shadow reports without
redownloading large canonical archives or rerunning workload locally. Earlier
archive replay was not substituted for new-source live qualification. Future
oracle changes still need qualification on their own source.

Rollback only the inspector reuse and its added tests, restoring uncached schema
parsing and matching documentation. Keep all suites, immutable format catalogs,
published hashes and retained measurements. No workflow disable, bypass,
timeout increase, changed workload or tag movement is part of this optimization.
