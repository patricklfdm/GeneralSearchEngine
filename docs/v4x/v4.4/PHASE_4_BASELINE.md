# GeneralSearchEngine V4.4 Phase 4 local hardening baseline

- **Status:** Local implementation complete; protected entry confirmed, Phase 4 acceptance pending
- **Phase 3 protected merge:** `b04e1e3a84a641131ef209826c64b43132efe737`
- **Phase 3 exact-master CI:** `34626677031` (`success`)
- **Decision:** `PASS_NO_MEASURED_REGRESSION`
- **Production/API/format/authority change:** None
- **Paid cloud execution:** None

## Frozen local workload

The Phase 4 probe is benchmark-only and runs in a separate JVM with `-Xms1g`,
`-Xmx1g`, G1, and a 240-second external deadline. It creates 20,000 deterministic
documents with four indexes, runs 2,000 single-writer durable updates while four
readers perform direct and indexed reads, checkpoints every 500 mutations, and
creates and structurally verifies a backup every two checkpoints. It then verifies a
complete document/query digest, performs three timed reopens, continues at sequence
2,021, and proves the continued state through a second reopen.

The Java probe owns scale, concurrency, checkpoint/backup cadence, semantic oracles,
reopen samples and resource observation. Four inherited deterministic V4.2 cases—two
catalog interruptions and two identity interruptions—own the separately reported
migration count. Phase 4 does not duplicate migration logic inside the scale probe.

## Local calibration receipt

The bounded development run completed on Linux/WSL2 with an uncontrolled local page
cache. It recorded 21,605,374 direct reads, 5,273 indexed searches, four checkpoints,
two backups, 27,258,575 retained bytes, 48,000,713 peak directory bytes, 46,899,337
final directory bytes, and three successful reopens with a 154,289,472 ns median.
The current and continued semantic digests differed as required and the probe
workspace was removed before the checksummed evidence bundle was written.

These values prove measurement wiring and bounded progress on this machine. They are
not portable throughput, latency, filesystem, device, page-cache, or cloud SLA
claims. Phase 6 remains the only owner of paid experiment/canonical evidence and the
paired published-4.3 release decision.

## Decision

No correctness failure or admitted measured regression was observed. The Phase 3
admission record remains empty, so Phase 4 makes no production optimization. The
strict validator rejects configuration drift, early termination, missing progress,
operation-cadence changes, invalid semantic digests, malformed reopen samples,
heap-limit violations, inconsistent disk peaks, or a hidden optimization decision.

Phase 3 entered protected `master` through PR #136. Exact-master CI run
`34626677031` passed on merge commit
`b04e1e3a84a641131ef209826c64b43132efe737`, satisfying the Phase 4 entry gate.

Run the complete local gate with:

```bash
scripts/verify-v44-phase4-hardening.sh
```

Phase 5 may now stabilize compatibility, artifacts, the canonical toolchain,
no-GCP cloud readiness, and the V5 handoff draft. It may not reinterpret this local
diagnostic receipt as accepted cloud evidence.
