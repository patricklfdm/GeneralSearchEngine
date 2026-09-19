# V5.0 release checklist

**Status:** Phase 7 candidate; Phase 8 publication has not started.

## Candidate identity

| Item | Frozen value |
| --- | --- |
| Final version | `5.0.0` |
| Artifacts | `general-search-engine`, `general-search-engine-processor`, `general-search-engine-replication` |
| Unsigned inventory | Nine main/sources/Javadoc JARs plus three POMs |
| Archive timestamp | `2026-09-19T00:00:00Z` |
| Java / Maven | Eclipse Temurin `21.0.12+8`, Maven Wrapper `3.9.11` |
| Container | `linux/amd64`, digest-pinned in [release-toolchain.json](release-toolchain.json) |
| Environment | `C.UTF-8`, UTC, umask `0022` |
| Artifact hashes | [Exact nine-JAR manifest](candidate-artifacts.sha256) |
| Cloud baseline | [v5.0.0-replicated-cloud](PHASE_6_BASELINE.md), measured snapshot source retained |

The candidate validator requires the exact sorted inventory and checks every hash.
The canonical receipt additionally binds both clean captures, all three POMs,
toolchain identity and source archive provenance. Main/sources/Javadoc artifacts
exclude admission workers, fault controls and evidence fixtures.

## Reproduce locally or in CI

```bash
scripts/verify-v50-phase7-release.sh
scripts/verify-v50-canonical-build.sh
python3 -m scripts.v50.candidate_artifacts validate-evidence target/v50-canonical-reproducibility
```

The default canonical command requires a clean committed checkout and a fresh output
directory. Candidate preparation before a user-owned commit may explicitly use
`--working-tree`; its receipt labels the source accordingly. The archived source is
built twice in separate directories using the pinned image and checksum-verified
Maven ZIP. A host-vendor build is diagnostic; its Javadoc bytes may differ. Hosted
release CI selects the matching Temurin version and must match all nine hashes.

## Local candidate validation record

- Full unsigned release reactor: 728 discovered tests, four existing tests requiring
  separate published-runtime baselines skipped; no failures or errors. Strict
  Javadocs and nine-JAR artifact inspection passed.
- Frozen source/reflection API passed. Published artifact/API comparison through
  V4.4 passed with fresh Maven dependencies and the exact approved additive V5 delta.
- V1–V5 consumers passed using an isolated Maven repository.
- V5 Python discovery: 288 tests passed; nine candidate/toolchain regression tests
  are included. A separate 23-test inherited release/change-scope suite passed.
- Two clean canonical builds matched all nine JARs and three POMs. The local receipt
  is `target/v50-canonical-reproducibility`, explicitly labelled `working-tree`;
  committed-source reproduction remains a required CI step.
- All 21 public-runtime process cases passed after rerunning the four bound Java
  suites for the test-worker change. Phase 6A passed 80 measured calls, 64 durable
  successes and all 21 semantic negatives. See the [Phase 7 checklist](PHASE_7_CHECKLIST.md).
  Local process testing exposed a
  test-only partial `barrier` publication race: the worker now writes a temporary
  file and atomically renames it before the controller can observe readiness.
  This changes no production class, public descriptor or cloud baseline.

## Phase 8 — after protected acceptance and explicit authorization

- [ ] Record the accepted master commit and successful exact-master CI.
- [ ] Confirm local/remote `v5.0.0` tag absence and Central HTTP 404 for all three coordinates.
- [ ] Create and verify the annotated signed tag at that exact commit; user pushes it.
- [ ] Release validation passes version/tag signature, consumers, API, packaging and canonical byte gates.
- [ ] Approve the `production-release` deployment; build/sign all twelve publishable files.
- [ ] Candidate hashes match before signing, after signing, before deploy and after deploy.
- [ ] Publish all three artifacts with signatures, sources and strict Javadocs.
- [ ] Download all twelve files plus signatures/checksums from Central into a fresh directory.
- [ ] Validate signature/checksum/manifest versions, exact nine canonical hashes and fresh V1–V5 consumers.
- [ ] Record Central deployment, GitHub deployment, workflow and GitHub Release identities.
- [ ] Update README/changelog to published status only after reconciliation.

Never overwrite an existing Central version or retarget a published tag. A partial
publication or polling failure requires inspection of exact remote coordinates and
hashes before recovery. No failed run is rewritten as success without that evidence.
