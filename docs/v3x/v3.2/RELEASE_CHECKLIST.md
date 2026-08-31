# GeneralSearchEngine 3.2.0 release checklist

This is the state-aware release record for V3.2. It distinguishes verified snapshot
evidence, final-candidate evidence, publication, and post-publication proof.

## Current state

| Field | Value |
|---|---|
| Target version | `3.2.0` |
| Active candidate | `3.2.0-SNAPSHOT` |
| Phase 6 entry commit | `fbbce30` |
| Snapshot-hardening branch | `feat/v3.2-phase6-release-hardening` |
| Final protected-master commit | `PENDING` |
| Signed tag | `PENDING` |
| Maven Central | `PENDING` |
| GitHub Release | `PENDING` |

Published `3.1.0` remains current stable until every publication and remote
verification item below is real.

## Frozen release contents

- additive `OffsetAnalyzer` and `OffsetAnalyzedToken` source-mapping capability;
- exact built-in `SimpleAnalyzer` UTF-16 source offsets with unchanged ordinary
  term/position output;
- immutable snapshot-bound `HighlightedSearchRequest` and structured result family;
- deterministic TEXT, PHRASE, FUZZY, BOOL, and BOOST evidence;
- no HTML, stored offset payload, sidecar, analyzer composition, synonym graph,
  stemming, ranked prefix, or new cloud benchmark family; and
- permanent Unicode, differential, lifecycle, mutation, concurrency, storage,
  allocation, and scale coverage.

## Snapshot candidate evidence

| Gate | Evidence |
|---|---|
| Version alignment | PASS — `3.2.0-SNAPSHOT` across seven active coordinates |
| Core clean verify | PASS — 343 tests, no failures/errors/skips |
| Reactor verify | PASS — 343 core, 5 processor; example compiled |
| API fixture | PASS — V1 reflection/source and V3.2 descriptor/source fixtures |
| Five-baseline Japicmp | PASS — final-tree fresh-isolated Maven repository with pinned V3 hashes |
| Independent consumers | PASS — V1/V2/V3 styles from isolated repository |
| Travel example | PASS — ranked, Explain, structured highlight, dynamic index |
| Strict Javadocs/release artifacts | PASS — six JARs and service-entry isolation |
| Reproducible six-JAR build | PASS — two clean builds byte-identical |
| JMH package/smoke | PASS — expanded V3.2 surfaces and production-soak instrumentation |
| Cloud Benchmark local gates | PASS — Python 3.11.15, 61 unit tests, shell/synthetic/fake-gcloud lifecycle |
| Diff hygiene | PASS |
| Protected PR/master CI | `PENDING` |

## Snapshot reproducible artifact hashes

Two clean builds of the snapshot candidate produced byte-identical artifacts:

| Artifact | SHA-256 |
|---|---|
| `general-search-engine-3.2.0-SNAPSHOT.jar` | `c8de06b6febc88d86612a3720ce7f5882d09b70b2469a83594095d51567919bf` |
| `general-search-engine-3.2.0-SNAPSHOT-sources.jar` | `1244bc0cb8c922c84b5d177b5a89b5e0496b0b25a7fa5ac0b19381c76e8d9fd9` |
| `general-search-engine-3.2.0-SNAPSHOT-javadoc.jar` | `f82810564aeda56ef20e5cfc7db18d518abf5f5e872a93161864392b00d3e7ef` |
| `general-search-engine-processor-3.2.0-SNAPSHOT.jar` | `3a08cd21ed53854267f55c77173465775698a241d6ea6467b6cf293be8e0f18c` |
| `general-search-engine-processor-3.2.0-SNAPSHOT-sources.jar` | `cdd160b655c79e2c98130cdf3370470e70fd856e0fabe7bcfc236b5d66a8b6d4` |
| `general-search-engine-processor-3.2.0-SNAPSHOT-javadoc.jar` | `1fed8584effc677884d75e58bb499af89361228d421437be22dfd8fede7e2e3c` |

Snapshot hashes are evidence only and are not the final published artifact identities.

## Final `3.2.0` candidate

- [ ] Start from the accepted snapshot-hardening merge on protected `master`.
- [ ] Convert all seven active project/consumer coordinates together.
- [ ] Freeze the output timestamp and dated changelog.
- [ ] Preserve published baselines and historical release records.
- [ ] Repeat every snapshot validation family.
- [ ] Record the six final reproducible JAR hashes.
- [ ] Merge through protected PR and record exact master commit and CI run.

## Signed tag verification

- [ ] Create annotated signed `v3.2.0` on the exact final protected-master commit.
- [ ] `git cat-file -t v3.2.0` reports `tag`.
- [ ] `git tag -v v3.2.0` verifies fingerprint
  `91AAB7A2B0FB55C3BBB334534B6103148D643AB3`.
- [ ] `scripts/verify-release-tag.sh v3.2.0` passes.
- [ ] `git rev-parse v3.2.0^{commit}` equals the recorded master commit.
- [ ] Push only after every local check passes.

## Protected publication

- [ ] Release validation checks out the exact tag and passes all release gates.
- [ ] Central immutability preflight confirms `3.2.0` does not already exist.
- [ ] The repository owner approves `production-release` after validation.
- [ ] The successful workflow/deployment IDs and exact commit are recorded.
- [ ] Core and processor main/sources/Javadoc/POM artifacts and all eight signatures
  publish successfully.
- [ ] `scripts/verify-published-release.sh 3.2.0` passes from a clean remote repository.
- [ ] GitHub Release `GeneralSearchEngine 3.2.0` is created from the verified tag and
  marked latest.

## Post-publication evidence

| Field | Value |
|---|---|
| Tag/master commit | `PENDING` |
| Signing fingerprint | `91AAB7A2B0FB55C3BBB334534B6103148D643AB3` |
| Release workflow | `PENDING` |
| Production deployment | `PENDING` |
| Central publication | `PENDING` |
| Clean remote verification | `PENDING` |
| GitHub Release URL/time | `PENDING` |

After publication, a documentation-only protected PR replaces every applicable
`PENDING` value with observed evidence, identifies `3.2.0` as current stable, and adds
the immutable published artifact as a future compatibility baseline. Until then, this
record makes no release claim.
