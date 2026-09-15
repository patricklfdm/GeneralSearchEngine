# V5.0 Phase 3 leader-path baseline

- **Status:** Accepted through protected PR #148
- **Branch:** `feat/v5.0-phase3-leader-path`
- **Coordinates:** `5.0.0-SNAPSHOT`
- **Starting master:** `1895598412b82da9de57655027d0ae76f75e327c`
- **Phase 2 acceptance:** [PR #147](https://github.com/patricklfdm/GeneralSearchEngine/pull/147),
  [exact-master CI 34934537274](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34934537274)
- **V4.4 control checksum:** `0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`

## Protected-master acceptance

[PR #148](https://github.com/patricklfdm/GeneralSearchEngine/pull/148) merged at
`911c9de0bd63149e5d48e7f4d5cb0ea7042a951e`. [Exact-master CI
34940262703](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34940262703)
passed all Required dependencies, including the three-JVM Phase 3 gate.

## Delivered boundary

The internal production node now activates one configured leader, replicates entries
and commit proofs over bounded real TCP, and publishes application state only after
proof quorum. Ordinary in-memory snapshot engines provide private validation and
atomic committed publication; no V4 WAL becomes a competing authority. Complete
matching-history restart uses a new epoch. Recovery divergence fails closed.

See [the leader-path design](PHASE_3_LEADER_PATH.md) for payloads, threading, limits,
read leases and failure semantics. Public builder/bootstrap admission remains reserved
until its recovery/bootstrap gate. Snapshot install, repair, compaction and paid cloud
are not part of this candidate.

## Validation

Final local candidate results (OpenJDK `21.0.12+8`, Maven `3.9.11`, Python `3.11.15`
for the gates, Linux WSL2; existing offline dependency caches):

- full clean release reactor: core 541 tests (4 skipped), replication 64 tests
  (45 existing storage/API cases, 14 leader cases and 5 wire/transport cases),
  processor 5 tests; no failures or errors;
- full V5 Python suite: 49 tests, including 4 new independent leader-oracle cases;
- Phase 1 model, separate-JVM and fake-cloud/evidence gate: pass;
- Phase 2 storage gate: 19 SIGKILL cases and 9 cross-language corruption cases pass;
- Phase 3 gate: 8 independent three-JVM TCP cases, including leader restart,
  one/two follower loss and 7 held SIGKILL publication/response barriers, pass;
- independently parsed histories/receipts and observed progress match the Phase 1
  model; negative cases reject absent proof quorum, counter drift and conflicts;
- zero-epoch handshake succeeds without mutation; unactivated APPEND rejects;
- injected worker-close rejection kills/reaps the exact JVM, releases its store
  lock and retains its exit record;
- independent V1–V5 consumers and published V1–V4.4 API/checksum comparison: pass,
  using retained isolated caches (no fresh remote-resolution claim);
- nine-JAR release integrity and test-worker/fixture exclusion: pass;
- two clean release builds: all nine JARs byte-identical, with their digests retained
  through subsequent validation; and
- Python compilation, shell syntax, 406 local documentation links and diff whitespace:
  pass. Core/processor source, public API inventories and storage golden bytes are unchanged.

The gate records source SHA and dirty-tree status, exact PIDs/lifetimes, raw request/
response controls, runtime events, crash markers, exit codes, pre-reopen replica copies,
SHA-256 inventories and independent/model reports. CI uploads `target/v50-leader`
even after failure. Uncommitted local results are explicitly candidate evidence and
do not replace exact-source PR/master CI.

Final generated local evidence (not committed; CI creates fresh source-specific runs):

- `target/v50-foundation/run.xMkM1k/`
- `target/v50-storage/run.Uxvm9n/evidence/`
- `target/v50-leader/run.HLzmEG/evidence/`
- `target/v50-leader/cleanup-rejection-f_eua1g1/`

Artifact validation uses unsigned local `5.0.0-SNAPSHOT` builds and is not a published
release or signed-release acceptance claim.

## Reproduction

```bash
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-v50-phase1-foundation.sh --skip-build
scripts/verify-v50-phase2-storage.sh --skip-build
scripts/verify-v50-phase3-leader.sh --skip-build
scripts/verify-consumer-projects.sh
./mvnw -Partifact-compat -DskipTests verify
scripts/verify-release-artifacts.sh 5.0.0-SNAPSHOT
```

The Java and Phase 3 process tests require permission to open loopback TCP sockets.
Maven can run offline with cached dependencies. Run the two-clean-build reproducibility
script before collecting `target` evidence, since clean removes generated workspaces.
No Git mutation or PR creation is part of these validation commands.

## Acceptance and next phase

Protected Phase 3 acceptance and exact-master CI passed as recorded above. Phase 4 implements
quorum reconciliation, incomplete-tail handling under proven authority, catch-up,
replacement-voter admission, immutable snapshot installation and safe compaction.
Public bootstrap/engine admission must be completed and reviewed against the frozen
API/authority contract before those entry points are enabled.
