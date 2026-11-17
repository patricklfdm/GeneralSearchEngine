# Retained-source whole-image validation

Phase 3 remains **OPEN**. The first maximum-native run
[44191186582, attempt 1](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/44191186582)
failed on source `60ad5a3a776ac58b7d6ae69a33ed5dac9f34babd` during initial activation.
The original JUnit error was `activation driver campaign capacity exhausted`.
The verify job correctly refused this incomplete original. This was not a
workflow timeout or the earlier host maintenance restart.

The retained diagnostics distinguish the first failure from cleanup errors:
the first two PREPARE replies arrived at 21.72 and 22.74 seconds from the first
request. SELECTED sends began at 237.38 and 247.83 seconds and exhausted their
unchanged three exchange attempts. A fresh ballot began at 691.65 seconds;
its PREPARE exchanges then expired. Later higher-ballot and endpoint-close
exceptions do not identify the initial cause. Failed originals remain retained.

## Redundant work and correction

`MembershipSourceReceive.recheck()` checks every borrowed original image.
Unlike current-prefix exports, retained-source exports still used the default
`checkImage()` implementation, which materialized a full image. Each 4 MiB piece
of that materialization invoked two complete owner checks. At the maximum image
size, each invocation therefore repeatedly reread and hashed all retained
sources, generations and ledgers while holding the journal monitor.

Retained-source validation now calls its existing physical `hasImage()` check.
That method checks export membership and the original deadline, and
`checkOwner()` calls `MembershipBasisSources.check()` to inspect every original
file's content digest, extent and inode. This includes supplemental older images
pinned by the export. The requested application digest and extent must match a
real retained member. No validation result is cached across calls.

A caller that actually needs the image still receives a fresh bounded byte array.
One whole-file read occurs under the same journal monitor, between the full
entry and exit checks. The read checks path/inode and length, hashes the returned
bytes, and rechecks the live owner/deadline before returning. It contains no
protocol callback, mutation or asynchronous boundary. External chunk reads keep
their 4 MiB cap and complete checks before and after each call.

## Verification and limits

Focused regressions compare whole-image validation work for a small image and
an image larger than two wire chunks, using an instrumented clock rather than
wall-time thresholds. They check physical validation without materializing a
second image, late byte/inode mutation, expiry and close before a whole-image
return. Existing supplemental-source tests also check changed originals and
expired borrows through `checkImage()`.

Against the original runtime, the three new regressions produced two expected
failures and no errors: whole-image clock checks increased from 8 to 16 as the
image grew beyond two chunks, and `checkImage()` used 8 clock checks instead of
the physical owner's 2. These are deterministic observations of repeated work,
not throughput measurements or a failover SLA.

The correction passed 59 focused Java tests: 18 prefix-discovery tests locally
and 41 source-export, source-receive, retained-image, whole-image and selected-pull
tests in an isolated copy on the dedicated Linux runner using Temurin 21.0.12+8.
All three new regressions passed. The initial local network attempt was blocked
by sandbox socket permissions; the subsequent local suite was stopped after
prefix discovery passed because filesystem forcing was slow. Those interrupted
runs are retained, not counted as passing suites. The runner's first offline
attempt lacked cached plugins; dependencies were downloaded before the complete
41-test execution. No formal large history was rerun during these component tests.
The 38 maximum-native Python tests and the V5.3 documentation contract also passed.
Reports and hashes are retained at
`target/v53-native-failure-44191186582/validation-summary.json`.

The first maximum-transition success remains evidence for its original source.
This runtime correction needs a fresh source-bound maximum-native run and does
not promote the failed original or establish a final-source combined cohort.
Reduced repeated work does not prove that all large-history timing failures are
resolved. Request deadlines, retry/campaign counts, resource limits, workload
parameters, persistent formats and wire semantics are unchanged.

Rollback restores the retained-source default `checkImage()` and its per-chunk
whole-image implementation. No data migration is required.
