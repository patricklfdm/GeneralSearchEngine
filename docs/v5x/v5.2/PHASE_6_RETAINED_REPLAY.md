# V5.2 original retained member and set replay

Phase 6BG connects the [native retention format](PHASE_6_NATIVE_RETENTION.md) to
independent authority, complete-history and five-member replay. It also supplies a
fixed GET-only restoration factory. These internal entries do not dispatch an
experiment, establish protected workflow acceptance, or deploy cloud identities.

## Original authority and physical replay

`cloud_member_authority` takes a separately selected request, exact source/JVM
binding and source-controlled configuration. It replays original provider and
permission observations, operator approval, protected build provenance, input
package and recent cleanup at the original admission time. It reconstructs the
thirteen resource identities, three guest identities and host-key pins, data-volume
readiness, installed Python/Java identities and every history's expected placement.
Copied result bindings are compared with that reconstruction, not used as their
own source of authority.

`cloud_member_evidence` requires the exact retained file inventory and hashes,
original successful completion, matching exact-ID cleanup, and the original
reservation/terminal ledger pair. Unexpected files and directories, private files,
symlinks, hardlinks, changed source/build inputs or partial histories reject.
Every selected history archive is unpacked into a fresh replay directory. Existing
physical, public-history, query, resource and negative validators inspect those
bytes. Results, call counts and archive hashes must equal the original retained
result; a retained PASS alone cannot satisfy validation. No workload is rerun.

The returned status is `MEMBER_REPLAYED_NOT_QUALIFIED`. Per-history detailed replay
outputs remain available; the member receipt records compact summaries and binding
hashes rather than duplicating all query inputs.

## Five complete members, any execution order

`cloud_set_evidence` requires experiment, failure-drill and canonical repetitions
1–3 from one source, checkout, sequence, build, package and published-control set.
All five original requests must already have successful terminal ledger entries.
Each complete member is independently replayed once; a failure stops the set and
preserves earlier outputs. Successful fragments from failed attempts cannot fill
missing histories.

Across all members it checks distinct original invocations, resource identities,
guest boots, groups, histories and manifest hashes. The complete set retains
33 histories, 27,428 reads, 2,760 updates and 2,700 nominal M01 offered seconds.
All 439 formal negative cases are required at this replay location. The existing
M01 cross-repetition artifact, compiled-consumer, profile and outcome checks also
run. Local M01 cohorts still require a single run/attempt. Cloud callers supply a
complete invocation map derived from each independently verified original member;
no invocation is inferred from the history it is intended to verify.

The result is `COMPLETE_SET_REPLAYED_NOT_QUALIFIED`. It distinguishes selected
successful reservations from total ledger reservations, including failed attempts.
Time and cost policy remain soft; no historical cost or failure is removed.

## Exact original object restoration

Completion records bind a cleanup hash. Cleanup now also retains an immutable copy
at `cleanups/<sha256>.json`, while preserving its original lease-generation record.
The wire policy checks that the content matches this name. Retrieval therefore
requires no object-list permission or guessing of lease generations. A failed
copy leaves completion pending; reconciliation preserves conservative failure
semantics and cannot grant workload acceptance.

`cloud_evidence_read` reads one ledger and selects the five explicit request hashes.
Only that ledger and each selected request's context, completion, addressed cleanup,
manifest and declared parts enter the GET allowlist. Media reads include both
`generation` and `ifGenerationMatch`; metadata is checked again after each object.
Object sizes, JSON fields, part coverage and hashes remain bounded. Missing or
changed objects stop restoration. An original read has a finite deadline; stage
time has no aggregate deadline and no business/workload retry is introduced.

A final ledger may append later attempts, but cannot rewrite the original prefix.
The downloader retains generations, byte hashes and the before/after snapshots.
Its native factory owns exact-workflow credentials and rechecks the clean source
and configuration. It provides no listing, mutation or arbitrary-URL operation.
Its status, `ORIGINALS_RESTORED_NOT_QUALIFIED`, is not full cloud acceptance.

## Validation scope and remaining entry work

The member, set and download unit suites exercise modeled provider/workload inputs,
including source/identity substitutions, missing members, reuse, physical-result
drift, partial downloads, generation changes, ledger rewrites and retained failed
costs. These models do not establish GCP behavior.

The unchanged local SSH/JVM smoke and SIGKILL/restart archives from source
`1f4a893bd39bd6f5e7b29e0ece399892e8d3cb7e` were replayed through the new helper.
They retain their original scope: 11 reads/3 updates and 4 reads/4 updates. Replayed
results equal the previously retained physical results. No new workload ran and
neither archive was relabeled as current-source cloud evidence. Four unchanged
formal archives from source `5d183cac51e44ad393fc3583158b3a7e868617be` also pass:
published V5.1 legacy strong and candidate explicit strong each retain 1,801
reads/180 updates; M02 above-1000 retains 31 reads/four updates; M03 p4 retains
five reads/four updates. The four original physical/oracle/negative results match
their retained receipts exactly (1,846.141 seconds locally, including contention
with unit models). This is replay time, not a new measurement or hosted estimate.
Logs, original failed fixtures and corrected tests live under
`target/v52-retained-replay`.

Before any paid dispatch, connect protected original Runner provenance and the
operator entry to these internal functions and review the undeployed V5.2
configuration and identity setup. [Required CI partitions](PHASE_6_CI_PARTITIONS.md)
now isolate Python validation and complete runtime commands without losing checks. Exact-source protected CI and all five real native members remain
required. No full cloud qualification is claimed here.
