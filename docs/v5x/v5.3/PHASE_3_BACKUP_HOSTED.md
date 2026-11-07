# Complete small-backup hosted qualification

This development entry transports the [complete verified-backup execution
profile](PHASE_3_BACKUP_EXECUTION.md). It uses the fixed three-document backup
at sequence 731 and one uninterrupted five-voter REPLACE history. It is not the
maximum-image history, the frozen EMPTY supplement or final Phase 3 acceptance.

## Execution and evidence boundary

`.github/workflows/v53-backup-resources.yml` is opt-in: manual dispatch on an
explicit branch, or push to `experiment/v53-backup-resources`. It does not join
ordinary CI or Required, request cloud credentials, or use a V5.2 runner. Its
three Ubuntu jobs are:

1. `prepare`: freeze source, compiled classes, reader, pinned tools and offline
   Maven dependencies. The existing preparation guard runs; the long native
   history does not. The seed is `PARTIAL`.
2. `execute`: download that seed and run the exact backup test once. There is
   no history retry, matrix split, shortening or stitching. The complete raw
   result remains `PARTIAL`, including a failure's receipt and diagnostics.
3. `verify`: download that exact seed and complete original, independently
   replay the original and require all 149 exact negative results. Recheck
   source/build/reader/tools, producer receipt and downloaded bytes afterward.

Artifact names and manifests bind source SHA, workflow, run and attempt. Both
seed and member receipts require `bootstrapSource=VERIFIED_DURABLE_BACKUP` and
`wireLayout=SEGMENTED_BACKUP`; these cannot select the consumer's policy. The
adapter explicitly selects `5-REPLACE-required-four-backup-segmented`. An EMPTY
artifact, a different workflow/attempt or a producer-only success cannot pass.
Failed/cancelled/skipped execution jobs cannot qualify. A new attempt must retain
its own complete history; rerunning only verification against another attempt's
artifacts is not an accepted shortcut.

Each stage emits progress every minute. The native lifetime and command are
unchanged, and the workflow retains the existing 360-minute job ceiling. Raw
evidence, diagnostics and verification receipts use 90-day artifact retention.
Failure is never converted into success by an upload or a replay-only receipt.

## Artifact capacity

The small-backup adapter uses streaming inventories with 1 MiB hash blocks;
both archive production and downloaded replay avoid the old eager whole-file
inventory. The seed retains its existing 1 GiB transport ceiling. Raw transport
has a 17 GiB ceiling: 16 GiB allowance for this small history plus 1 GiB for
immutable source/build and diagnostics. This is an explicit development-host
admission bound, not a measured size or a change to any runtime resource budget.
The segmented reader's 128 GiB original-format ceiling is unchanged. This
workflow does not promise to transport every original admitted by that ceiling.

Execution requires 40 GiB free before copying the seed and starting the history:
space for up to 17 GiB unpacked data, a worst-case compressed copy and 6 GiB
workspace margin. Verification checks 40 GiB before download, then 23 GiB before
extraction. Checks read the actual workspace filesystem. They do not reserve
space or establish peak-memory capacity. The Java command retains its 4 GiB
heap setting. Maximum-input and simultaneous-resource acceptance still require
their separate, adequately provisioned runner and actual measurements.

Over-capacity archives fail without truncating originals or deleting earlier
attempts. Execution retains its primary error even if subsequent artifact
packing also fails. When packing cannot finish, diagnostics identify both
failures; an artifact upload is not guaranteed under exhausted storage. Archive
readers reject unsafe members, changed hashes and a mismatched manifest.

## Development validation and remaining work

The [development index](phase3-evidence/backup-hosted-development.json) separates
synthetic binding/rejection tests and retained-prefix transport checks from
actual native qualification. The retained prefix is incomplete and is not a
hosted seed/member or a positive complete backup history.

This batch does not push or dispatch the workflow. Complete backup execution and
the independent real 149-negative replay remain pending. A future successful
result may claim `required-four-backup-observed-ownership` only;
`combinedResourcesQualified`, final-source acceptance and `phase3Complete`
remain false. Existing EMPTY workflows and cohort identifiers are unchanged.

Rollback removes this independent workflow, adapter, disk admission and their
tests/documentation together. Retain any original attempts and their manifests.
No production runtime, durable format, POM, Required or frozen cohort rollback
is needed.
