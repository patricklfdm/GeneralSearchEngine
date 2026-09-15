# V5.0 Phase 2 replicated storage baseline

- **Status:** Accepted through protected PR #147
- **Branch:** `feat/v5.0-phase2-replicated-storage`
- **Coordinates:** `5.0.0-SNAPSHOT`
- **Starting master:** `2e78bddd37fff6638c621da4e4f7f27c3f85a8aa`
- **Phase 1 acceptance:** [PR #146](https://github.com/patricklfdm/GeneralSearchEngine/pull/146),
  [exact-master CI 34930568130](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34930568130)
- **Published V4.4 control SHA-256:** `0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`

## Protected-master acceptance

[PR #147](https://github.com/patricklfdm/GeneralSearchEngine/pull/147) merged at
`1895598412b82da9de57655027d0ae76f75e327c`. [Exact-master CI
34934537274](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34934537274)
passed all Required dependencies, including the Phase 2 production-storage crash gate.

## Delivered behavior

The optional replication artifact can initialize internal local storage, persist and
reopen epoch promises, append opaque entries, store received commit proofs and inspect
closed authority without a codec. The public inspector is enabled; the exact public
API signatures are preserved by allowing package-private implementation classes
behind the frozen public inventory.

The [format specification](PHASE_2_STORAGE_FORMAT.md) freezes the binary envelope,
manifest/identity bindings, three journals and initialization marker. Exact retries
force without adding records; rejected requests do not write. I/O failure stops new
writes until reopen. Every authoritative file is bounded, checksummed and validated;
corrupt or partial tails reject without automatic repair.

Python independently writes/reads the format. Its golden directory and the Java
writer produce identical bytes. The populated example contains log indices 1–3,
local CommitIndex 2, promised epoch 2, and no applied application state. A local proof
is never presented as proof quorum or a successful application operation.

## Candidate validation

Final local candidate results (OpenJDK `21.0.12+8`, Maven `3.9.11`, Python `3.11.15`,
Linux WSL2; dependencies resolved from existing local caches):

- full clean release reactor: core 541 tests (4 skipped), replication 45 tests
  (37 storage cases), processor 5 tests; no failures/errors;
- full V5 Python suite: 45 tests, including 7 independent storage-format tests;
- existing Phase 1 three-JVM/model/fake-cloud/evidence gate: pass;
- real production-storage crash gate: 19 SIGKILL cases;
- cross-language corruption gate: 9 malformed directories;
- cross-process writer ownership and lock release after kill: pass;
- published V1–V4.4 API artifact/checksum comparison: pass using the retained isolated
  dependency cache (no fresh remote-resolution claim);
- independent V1–V5 consumer compilation/tests: pass;
- nine-JAR release integrity, including test-worker/fixture exclusion: pass; and
- two final clean release builds: all nine JARs byte-identical.

The Phase 2 gate stores source SHA and working-tree status, exact PIDs/barriers,
process exit signals, worker logs, copied pre-reopen bytes and hashes, independent
pre-reopen reports, Java reopen reports and the aggregate result. CI retains
`target/v50-storage` with `always()` upload. Candidate results from an uncommitted
working tree are explicitly marked dirty and are not exact-source release evidence.

The final local storage evidence is under
`target/v50-storage/run.oh4Ima/evidence/`. This generated directory is not committed;
CI produces a fresh evidence directory for the PR source.

## Reproduction

```bash
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-v50-phase1-foundation.sh --skip-build
scripts/verify-v50-phase2-storage.sh --skip-build
scripts/verify-consumer-projects.sh
./mvnw -Partifact-compat -DskipTests verify
scripts/verify-release-artifacts.sh 5.0.0-SNAPSHOT
```

`MAVEN_ARGS='-Dgpg.skip=true' scripts/verify-reproducible-build.sh` compares two clean
release builds. Run it before collecting local gate artifacts because clean removes
`target`. Add `-o` only with all required dependencies already cached.

## Limits and next boundary

The SIGKILL gate proves process-crash behavior on the local filesystem. It does not
simulate OS/device power loss, remote receipt authentication, quorum availability or
application/search-state equivalence. Internal initialization is not an accepted
group-bootstrap workflow. Entries remain opaque; no V4 engine materialization exists.

Protected Phase 2 review and exact-master CI passed as recorded above. Phase 3 implements
configured-leader quorum replication and ordered apply/publication using this local
storage boundary. Snapshot installation and suffix recovery/repair remain Phase 4.
No paid cloud resource, commit, push or PR was created during local implementation.
