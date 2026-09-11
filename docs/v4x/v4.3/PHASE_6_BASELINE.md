# GeneralSearchEngine V4.3 Phase 6 implementation baseline

- **Branch:** `feat/v4.3-phase6-performance-evidence`
- **Base:** `e241e1499861e0b44583a948d410ce0ac9c3c286`
- **Version:** `4.3.0-SNAPSHOT`
- **Production behavior:** unchanged
- **Status:** Canonical evidence accepted; append-only registration under protected review
- **Canonical source:** `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6`
- **Paid execution:** accepted experiment and canonical runs complete

## Implementation boundary

The Java probe owns only benchmark instrumentation. It produces paired current
forced-rebuild and complete-warm samples after backup publication, so the warm sample
cannot accidentally measure a catalog invalidated by the backup checkpoint. The
published `4.2.0` control is compiled only against its checksum-pinned Maven Central
JAR and must produce the same logical oracle.

The local assembler validates all ten cells, exact fallback counts, checksums,
sequences, duration and metrics, then writes the frozen checksummed bundle. The
independent Python `(1,2)` reader now accepts production backup sequences and bounded
checkpoint payloads while retaining the immutable Phase 2 fixture checks.

The cloud lane is manual, exact-source, short-lived-OIDC and serial. It uses a source
VM followed by a replacement VM, two independently retained data disks, bounded logs,
strict cleanup receipts, a human-readable preflight summary and a separate aggregate
set. Canonical threshold enforcement exists in both member and set validation.

## Acceptance command

```bash
scripts/verify-v43-phase6-evidence.sh
```

Cloud experiment/canonical run IDs and the three-member review are recorded below.
The canonical review merged through protected PR #128 as `ae25c80`, and exact-master
CI run `34567122915` passed. The separate append-only registration is now under
protected review.

## Local acceptance result

The complete Phase 6 gate passed after rebuilding the JMH probe, resolving and
checksum-verifying the published `4.2.0` control, exercising a real local `(1,2)`
store through all ten cells, independently parsing the production backup, and
re-validating the checksummed bundle. The stricter offline validator also rejects
semantic tampering even when an attacker regenerates the bundle checksum.

The full reactor passed with 537 core tests (4 skipped) and 5 processor tests. The
JMH smoke matrix, release-profile reactor, version alignment and release-artifact
integrity gate also passed; the latter accepted six JARs at `4.3.0-SNAPSHOT`.
Independent V1/V2/V3/V4 consumers compiled, and two clean release builds produced
identical hashes for all six JARs. Inherited Phase 5 lifecycle/cleanup and Phase 4
text/fallback crash gates passed in the final Phase 6 run. No OIDC token, cloud
resource, GCS object or paid execution was requested by these local checks.

## Rejected cloud bootstrap attempt

The first exact-source experiment attempt, GitHub Actions run `34545524731` at
`6686ba1870a7eec7c49c293f587e66caba61d1f3`, is not performance evidence. The source
host checked out the exact commit and formatted both data disks, but the clean Ubuntu
image lacked `unzip`; Maven Wrapper therefore rejected its checksum-pinned Maven ZIP
before any Java probe ran. Its receipt records `runStatus=FAIL` together with
`sourceVmDeleted=PASS`, both disk deletions `PASS`, staging-object deletion `PASS` and
aggregate `cleanup=PASS`.

The correction makes `unzip` an explicit remote bootstrap dependency and adds a
regression test proving that installation precedes the first `./mvnw` invocation.
Phase 1 and Phase 6 gates pass with the correction. A new exact-source experiment is
required after the correction merges and its protected-master CI succeeds.

The next exact-source experiment attempt, run `34548506759` at
`1151b7c1a5441ca5d0e1182208b2a9fd19f6d4f2`, proved that the wrapper correction and
published `4.2.0` production control passed. It then failed before the current-source
probe because the remote script passed nonexistent `primary/current` and
`target/current` children instead of the already-mounted roots required by the probe.
It is also not performance evidence. Its receipt records `runStatus=FAIL`, source VM
deletion `PASS`, replacement VM `NOT_APPLICABLE`, both disk deletions `PASS`, staging
deletion `PASS` and aggregate `cleanup=PASS`.

The mount-layout correction passes the two mounted roots directly, copies the backup
from its actual root-relative location, and locks the source, replacement, backup and
archive paths in regression tests. Phase 1 and Phase 6 gates passed after this
correction, which then merged and supplied the exact source for the accepted runs.

## Protected implementation acceptance

Phase 6 implementation merged through protected PR #125 as
`6686ba1870a7eec7c49c293f587e66caba61d1f3`; exact-master CI run `34538794639`
passed. The clean-host Maven-wrapper prerequisite correction merged through protected
PR #126 as `1151b7c1a5441ca5d0e1182208b2a9fd19f6d4f2`. The mount-layout correction
merged through protected PR #127 as
`1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6`; exact-master CI run `34550893252`
passed.

The WIF condition retains the exact repository, repository ID, owner ID, protected
master ref and `cloud-benchmark` environment predicates while adding only
`.github/workflows/v43-fast-reopen-evidence.yml@refs/heads/master`. A custom role
containing only `storage.objects.delete` is condition-bound to the exact
`v4.3-fast-reopen/` bucket prefix; create and read retain their existing permissions.

## Accepted cloud evidence

| Evidence | Reviewed value |
|---|---|
| Experiment | `34551484690 / attempt 1 / one member / actions` |
| Canonical | `34557940276 / attempt 1 / three serial members / gcs` |
| Exact source | `1d59ba9c354f5ea5ca4ebc8d8b5b30519479aac6` |
| Machine / zone | `c3d-standard-30 / us-west4-a` |
| Workload | `100000 documents / 16 tokens / 4 indexes / 10000 mutations` |
| Measurement | `1800 seconds per member` |
| Primary / target disks | two distinct `pd-balanced` 200-GiB ext4 disks |
| Suite / preset | `v4.3-fast-reopen-suite-v1 / v4.3-fast-reopen-v1` |
| Canonical ratios | `median 0.256803 / maximum 0.260551` |
| Canonical set SHA-256 | `b91f780d8f630d626f8aec3bc090073a5c4bbd9273819bc437d07c10ff7200c4` |
| Eventual baseline | `v4.3.0-fast-reopen-cloud` |

The experiment member, all three canonical members and both aggregate sets passed
independent checksum and semantic validation. Every canonical member completed all
ten cells, matched the published-4.2 logical control, proved warm and selective/full
fallback paths, reopened restored and migrated targets, and continued on a
replacement VM. Both VMs, both disks and staging objects report complete cleanup for
every accepted member.

The canonical members are comparable and `canonicalEligible=true`. Their evidence
digests and backup identities are distinct; all member ratios satisfy the `0.65`
bound and the set median satisfies `0.50`. GCS retains all three member mirrors and
the aggregate set under the exact source/run/profile prefix. Detailed identities and
bounded observations are recorded in
[`PHASE_6_CANONICAL_REVIEW.md`](PHASE_6_CANONICAL_REVIEW.md). These measurements are
diagnostic evidence on the pinned configuration, not an SLA.

## Registration candidate

The separate candidate appends exactly one `v4.3.0-fast-reopen-cloud` entry binding
the accepted source, suite, preset, three-member count, median ratio and set digest.
The registrar rejects duplicate, renamed or non-canonical input. Phase 7 remains
blocked until this registration PR merges and exact-master CI passes.
