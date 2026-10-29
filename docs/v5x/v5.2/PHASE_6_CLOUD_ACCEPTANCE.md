# V5.2 protected cloud set acceptance — 2026-10-29

**Status:** protected complete-set acceptance passed; this registration and the
[Phase 6 checklist](PHASE_6_CHECKLIST.md) are ready for operator merge.
The [Phase 7 release work](PHASE_7_CHECKLIST.md) remains open. Stable stays 5.1.0;
the measured candidate is 5.2.0-SNAPSHOT.

## Verified result and source boundaries

[Run 40841038976, attempt 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40841038976)
executed `verify-set` on protected master
`8b9aa60ab0cc9253046b162f28c40d47ae2acc82`, using the dedicated self-hosted
`gse-v52-cloud-d-wsl` Runner and Temurin `21.0.12+8-LTS`. The complete job and all
its steps succeeded. The job lasted **13,008 seconds (3 h 36 m 48 s)**;
the operation step lasted 12,946 seconds. These are verification durations,
not original measurement windows or cumulative cloud VM time.

The original [cloud-set receipt](phase6-cloud-review.json) is preserved byte for
byte. Its SHA-256 is
`01f9e744ecc311dd4777de768de7a44dc30078c72858e1ad8638ce8b63168c1f`.
It reports `status=PASS`, `fullRemoteQualification=true` and
`execution=native-v52-complete-set-replay`. `paidCloud=false` describes this
read-and-replay operation; the original workload executions used paid GCP VMs.

| Coverage | Verified count |
| --- | ---: |
| Logical members: three canonical repetitions, failure drill, experiment | 5 |
| Whole execution units: nine canonical shards, five drill shards, experiment | 15 |
| Complete histories | 33 |
| Formal M01–M04 histories | 28 |
| Additional untimed experiment histories | 5 |
| Original reads / updates | 27,428 / 2,760 |
| Nominal M01 offered seconds | 2,700 |
| Formal negative cases at the independent replay location | 439 |

The native join restored every original manifest and declared part, authenticated
each selected GitHub invocation, replayed every member and applied the full-set
checks. It checked authority, exact-ID cleanup, artifact/configuration identity,
history/query/physical results, negative cases and distinct original resources.
Its final source check passed. Registration here inspects that protected result;
it does not claim a second new physical replay or a new paid experiment.

The acceptance source above is the verifier source. The two measured sources are:

- **A:** `f6d7aad945b59e2c69989d4da7fd4b814080b7bf`, sequence
  `c3843899543949178ab16475342368cf` (the nine canonical shards and first drill).
- **B:** `0cbcfbcb3bec76f4f751e9cf720e0df2adfcce27`, sequence
  `87900804eccc4769a000f0a7dd1e53ff` (the remaining four drills and experiment).

The [quota continuation](PHASE_6_QUOTA_CONTINUATION.md) authorizes only this
batch. Its five executable JAR pins, program, suite and published controls remain
fixed. Different checkout/build/package bindings retain their true values in the
receipt. Neither the verifier nor this later documentation commit is relabelled
as a measured source. Original Cloud Build admission is not called full CI.

| Execution unit | Original run (attempt 1) | Source | Original closure |
| --- | --- | --- | --- |
| canonical-1-legacy | [40264837271](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40264837271) | A | PASS |
| canonical-1-explicit-stale | [40300349030](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40300349030) | A | PASS |
| canonical-1-minimum | [40393177611](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40393177611) | A | PASS |
| canonical-2-legacy | [40412651432](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40412651432) | A | PASS |
| canonical-2-explicit-stale | [40432675674](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40432675674) | A | PASS |
| canonical-2-minimum | [40457372190](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40457372190) | A | PASS |
| canonical-3-legacy | [40484706990](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40484706990) | A | PASS |
| canonical-3-explicit-stale | [40539710816](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40539710816) | A | PASS |
| canonical-3-minimum | [40594546865](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40594546865) | A | PASS |
| failure-drill-m02-below | [40614296775](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40614296775) | A | PASS |
| failure-drill-m02-equal | [40650622986](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40650622986) | B | PASS |
| failure-drill-m02-above | [40726281735](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40726281735) | B | PASS |
| failure-drill-m03 | [40754752865](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40754752865) | B | PASS |
| failure-drill-m04 | [40782369257](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40782369257) | B | PASS |
| experiment | [40809895634](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/40809895634) | B | FAIL; explicit retention exception |

## One-run retention exception

The [operator-authorized recovery](PHASE_6_RETENTION_RECOVERY.md), accepted through
[PR #363](https://github.com/patricklfdm/GeneralSearchEngine/pull/363), applies only
to the experiment above. All five histories completed, but a retention GET
exhausted its request deadline. The original manifest already bound 30 files
(131,426,342 bytes) and 55 parts. The Runner archive preserved all original bytes;
collection verified them, then create-only uploads restored the missing 21 parts
and read them back. The complete-set run independently replayed them afterwards.

The receipt explicitly preserves the original failed job, FAIL completion,
failed ledger entry and recovered part ordinals 34–54. The exception grants
neither general failed-run acceptance nor permission to splice incomplete
histories. Other batches retain their ordinary source/sequence and successful
original closure rules. Neither this exception nor the quota continuation is a
release-candidate CI waiver.

## Retention, accounting and interpretation

[Provenance](phase6-cloud-provenance.json) retains the authenticated run/job and
artifact metadata, original fifteen request/run/artifact/object pins, policy
hashes at the verifier source, and five JAR pins. The
[baseline registry](cloud-benchmark-baselines.json) binds that provenance and the
unaltered protected receipt. Compact files are an index to the originals, not
replacement evidence from which raw history can be reconstructed.

- Result artifact: `v52-cloud-set-40841038976-1`, ID `12895590148`, 3,789 bytes,
  SHA-256 `88aa534d729a4f147e5ee65019c649a8c59260e429750bf4f922ae3ba074dbcf`.
- Diagnostics/report artifact: `v52-runner-diagnostics-40841038976-1`, ID
  `12894268838`, 1,563 bytes, SHA-256
  `40a6abfeffe34e1fff67424413d97ef28782d72a16a237b2a06b9993ac3509b1`.
- GitHub reports both artifacts expire at **2027-01-27T08:17:09Z**, under the
  existing 90-day policy. Their verified original ZIPs and API/log records are
  retained locally under `target/v52-cloud-operations/verify-set-40841038976-1/`.
- The Runner completion hook recorded `self-hosted-preserved`. Full restored and
  replay evidence remains in the D-backed Runner archive at
  `/home/gse-runner/evidence-archives/40841038976-1/evidence` inside `GSE-Runner`.
  Preserve/export that archive before any Runner reset. Original GCS manifests
  and parts retain their original paths; the compact registry does not extend
  GitHub or GCS retention automatically.

The selected fifteen reservations total **USD 375**; the observed full ledger
totals **USD 1,780**, including historical attempts. These are conservative
reservation amounts, **not actual provider billing**. No cost/failure was reset
or refunded by verification or registration. Time and cost thresholds remain soft.
All thirteen resource absences for each original are part of historical replay;
this result is not a fresh project-wide resource inventory or another run's
cleanup admission.

PASS means the frozen histories and permitted outcomes satisfy their oracles. It
does not mean every offered call succeeded. The receipt retains explicit
rejections, indeterminate updates and legacy validation failures, including the
published control's outcomes. It establishes neither production throughput nor a
general latency/failover SLA. Component receipts such as M01 retain their limited
scope; the top-level protected join alone grants full remote qualification.

## Closeout and next work

Merge this registration to close the Phase 6 review boundary, then execute
[Phase 7A](PHASE_7_CHECKLIST.md): reuse and extend the existing seventh consumer,
review packaged compatibility/migration/API/Javadoc behavior, and connect the
accepted baseline to release tooling. Phase 7B freezes final coordinates and
canonical release bytes. Publication remains separately authorized.

The original recovery verifier deliberately rejects a later changed tree. Do not
rerun its exact-source entry on this documentation commit or widen its source
allowlist just to make that possible. Reuse the recorded protected result at
`8b9aa60a`; any new verifier or production change requires its own review. The
source-guard unit fixture is independent of the moving repository HEAD, so later
documentation or release work does not pretend to be the frozen accepted tree.

## Registration validation

The local registration check correlates the authenticated original ZIP bytes,
run/job/artifact metadata, all fifteen selections and source/build bindings,
counts, historical policy hashes and explicit exception/accounting fields. The
review file is the exact original receipt, not a reconstructed PASS. The two
documentation contracts and changed local links pass.

All 28 quota-continuation/retention-recovery tests pass. A simulated later HEAD
with one added closeout document reproduces the old test's false failure. The
independent tree fixture passes that same regression while still rejecting added
paths, changed support bytes, changed POMs and missing files. Only the test's
support-file hash is refreshed; the production tree fingerprint, frozen policy
core and runtime checkers are unchanged. Provenance above retains the policy
bytes from the accepted verifier commit, not this later test-hash update.

Local review scripts/logs are under `target/v52-phase6-closeout/` in the isolated
closeout worktree. No Maven build, workload, paid dispatch or new full CI was run
to prepare this registration. The operator's standing V5.2 cloud-support CI-skip
instruction remains separate from Phase 7 candidate validation.
