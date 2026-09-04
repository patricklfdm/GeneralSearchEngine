# GeneralSearchEngine V4.2 Phase 6 local pre-cloud baseline

- **Status:** Local implementation candidate; protected and paid acceptance pending
- **Source:** `feat/v4.2-phase6-performance-evidence` working tree
- **Reference:** Accepted Phase 5 commit
  `5687a05aa2f495f58d8acc904ab1e663361cf6e3`

## Focused gate

```bash
scripts/verify-v42-phase6-evidence.sh
```

The focused gate passed locally. It:

- builds the benchmark-only operational probe;
- verifies the pinned Maven Central `4.1.0` JAR checksum;
- compiles the rollback helper only against that published JAR;
- runs a bounded real `(1,0)` source, backup, typed migration, `(1,1)` target
  continuation/reopen and published-4.1 source rollback;
- validates checksummed source, migration, target, rollback and aggregate evidence;
- tests exact experiment/canonical/failure-drill plans and readable summaries;
- simulates a partial cloud-resource creation failure and proves cleanup ownership;
- validates strict serial/quota, GCS, workflow, registration and tamper boundaries;
- exercises all no-GCP fake profiles and the paid runner dry-run; and
- reruns the complete Phase 5/4/3/2 acceptance chain.

## Complete local acceptance

The clean reactor passed 500 core tests and 5 processor tests with no failures; only
the two published-artifact probes owned by the isolated compatibility profile were
skipped. The Phase 6 gate then rebuilt `target/benchmarks.jar` from the clean tree and
completed the full evidence chain described above.

## Local observations

- the source and target use distinct histories and directory identities;
- the source directory hash remains unchanged across migration and target operation;
- the target accepts continued writes and survives checkpoint plus second reopen;
- the untouched source reopens under the exact published `4.1.0` artifact;
- a simulated create-failed-after-allocation path deletes the discovered owned disk;
- canonical set assembly requires three serial comparable members with distinct plan
  and target-history identities; and
- duplicate registration and non-canonical registration fail closed.

No Google Cloud resource was created and no IAM or registry state was changed by this
local baseline. The tracked registry remains intentionally empty until canonical
evidence is reviewed.

## Pending acceptance

Protected PR checks, exact-master CI, WIF authorization, the paid experiment, the paid
canonical set, independent download validation and append-only registration remain
open. This document must not be interpreted as cloud performance evidence.
