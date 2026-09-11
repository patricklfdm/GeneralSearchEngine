# GeneralSearchEngine V4.3 Phase 6 implementation baseline

- **Branch:** `feat/v4.3-phase6-performance-evidence`
- **Base:** `e241e1499861e0b44583a948d410ce0ac9c3c286`
- **Version:** `4.3.0-SNAPSHOT`
- **Production behavior:** unchanged
- **Paid execution:** not yet authorized or performed

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

Cloud experiment/canonical run IDs, three-member review and the append-only registry
entry remain intentionally blank until the implementation PR is accepted on
protected `master` and its exact CI succeeds.

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
archive paths in regression tests. Phase 1 and Phase 6 gates pass after this correction;
a further experiment still requires merge and exact protected-master CI first.
