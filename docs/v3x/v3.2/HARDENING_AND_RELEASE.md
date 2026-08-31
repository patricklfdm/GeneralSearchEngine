# V3.2 Phase 6 hardening and release contract

## Boundary

Phase 6 freezes the completed V3.2 offset-analysis and structured-highlighting
capability set and proves that it is correct, compatible, documented, reproducible,
and safely publishable as `3.2.0`. It is a release-hardening phase, not a feature
phase.

The only permitted production behavior change is a minimal fix for a demonstrated
release blocker. Such a fix requires a failing regression test, a narrow implementation
change, targeted validation, and every applicable Phase 6 gate. Stored offsets, HTML
rendering, analyzer composition, synonyms, stemming, ranked prefix, broad refactoring,
and speculative optimization remain outside this phase.

## Ordered evidence states

Phase 6 starts from protected `master` after Phase 5 acceptance. Unlike V3.1, the
active project identity already changed atomically to `3.2.0-SNAPSHOT` in Phase 1.
Phase 6 therefore has four ordered states:

1. **Snapshot hardening** — retain `3.2.0-SNAPSHOT`; audit the complete public diff,
   consumers, documentation, release automation, inherited evidence, artifacts, and
   reproducibility; pass every local gate and merge through protected CI.
2. **Final release preparation** — from the accepted snapshot merge, change every
   current coordinate atomically to `3.2.0`; freeze the dated changelog and output
   timestamp; repeat every final-version gate; merge the approved candidate to
   protected `master`.
3. **Signed-tag publication** — create and locally verify annotated signed `v3.2.0`
   on the exact accepted protected-master commit, then let the protected Release
   workflow publish both artifacts and create the GitHub Release.
4. **Post-publication verification** — verify Maven Central from a clean repository,
   the published consumer, signatures, checksums, manifests, service entries, and the
   GitHub Release; record real evidence in a documentation-only follow-up.

Evidence from a later state must not be marked in an earlier state. A green final tree
is release-ready, not released. Tag, deployment, Central, remote-resolution, and
GitHub Release fields remain `PENDING` until those events exist.

## Frozen V3.2 supported API

V3.2 adds the supported analysis types:

```java
OffsetAnalyzer extends Analyzer
OffsetAnalyzedToken(String term, int positionIncrement,
                    int startOffset, int endOffset)
```

It adds one default engine capability and six immutable search result/request types:

```java
SearchEngine.search(HighlightedSearchRequest<T>)

HighlightedSearchRequest<T>
HighlightedSearchResult<T>
HighlightedSearchHit<T>
FieldHighlight
HighlightFragment
HighlightSpan
```

`Analyzer` remains a functional interface with one abstract method, and
`AnalyzedToken` retains its two published record components. Existing third-party
engines inherit a null-checking default method that otherwise reports unsupported
capability. Existing analyzers remain valid for every ordinary path and fail only when
their exact field is explicitly requested for highlighting.

The concrete `SnapshotSearchEngine` override and the Javadoc-hidden
`SearchExecutionAccess.searchHighlighted` sibling-package bridge are implementation
consequences of the supported default method, not separate application SPIs. Offset
validation, evidence collection, witness selection, fragment assembly, plans,
postings, snapshots, and internal document IDs remain unsupported internals.

The complete constructors, generic descriptors, defaults, validation timing,
immutability rules, and unsupported surface are frozen in
[API compatibility](API_COMPATIBILITY.md). No public signature may change during
Phase 6 without a contract amendment.

## Correctness and compatibility hardening

The permanent Phase 2–5 suites must retain:

- exact ordinary/offset term and logical-position equivalence, including randomized
  Unicode, normalization expansion/contraction, surrogate boundaries, gaps, and
  malformed output;
- canonical hit identity between ordinary and highlighted execution, including score
  bits, ordering, limit, filters, and failure precedence;
- independent TEXT, PHRASE, FUZZY, BOOL, and BOOST evidence oracles;
- deterministic phrase witnesses, scoring-selected fuzzy expansion, range merging,
  fragment windows, caps, and exact source substrings;
- add/update/remove/bulk, dynamic-index replay/drop/create, close admission, failure
  atomicity, and mixed reader/writer snapshot isolation;
- no offset analysis in indexing, ordinary search, Explain, or dynamic-index build;
  and no retained offset, highlight, evidence, or sidecar payload in text snapshots.

Japicmp compares the candidate against published `1.0.0`, `2.0.0`, `2.1.0`, pinned
`3.0.0`, and pinned `3.1.0`. The two pinned V3 artifacts must match their recorded
SHA-256 identities, and at least one run must use a fresh isolated Maven repository.
V1-, V2-, and V3-style consumers, the processor, generated sources, and the travel
example compile and execute only through supported APIs.

## Performance evidence inheritance

Phase 5 already froze the required local V3.2 evidence: top-K, requested-field,
source-length and corpus scaling; no-hit behavior; grouped highlighted/ordinary/
Explain/writer concurrency; allocation; and retained-memory inspection. Profiling
found no justified narrow production optimization. The remaining cost is canonical
ranking or the explicit top-K requested-source work required by the contract.

Phase 6 may inherit that evidence only while the production implementation, JMH
workloads, JVM/toolchain assumptions, index shape, and evidence identity remain
unchanged. Documentation, consumers, and aligned Maven metadata do not invalidate it.
Any performance-sensitive blocker fix requires renewed applicable evidence.

No paid cloud run is required for V3.2 release because V3.2 introduces no cloud
preset, workflow, immutable baseline family, stored offset payload, or ordinary index
shape. Local highlighting evidence is intentionally not registered as a canonical
cloud comparison family.

## Documentation and release-facing state

Snapshot hardening finalizes:

- a 3.1-to-3.2 migration path covering offset analyzers, structured results, legacy
  analyzer capability failure, UTF-16 ranges, markup ownership, and compatibility;
- the architecture, offset, highlighting, API, validation, evidence, hardening,
  checklist, and release-record links;
- a V3 consumer and travel example using highlighted search through supported APIs;
- `README.md`, `docs/README.md`, `docs/v3x/README.md`, both roadmaps, and
  `CHANGELOG.md` so they describe actual snapshot state.

Until successful publication, root installation guidance continues to identify
published `3.1.0` as stable. Development examples may identify `3.2.0-SNAPSHOT`
explicitly, but must not imply Maven Central availability. Historical V3.0 and V3.1
release records remain immutable.

## Artifacts, reproducibility, CI, and publication

The existing protected CI and Release workflows are reused. Required CI retains
reactor tests, five-baseline compatibility, independent consumers, release packaging,
artifact inspection, reproducibility, benchmark smoke, and cloud-runner validation.

Only `general-search-engine` and `general-search-engine-processor` are publishable.
Each publishes its POM plus main, sources, and strict Javadoc JARs. The core JAR has no
annotation-processor service entry; the processor JAR has exactly the expected entry.
Reactor aggregators, examples, compatibility consumers, benchmarks, and test fixtures
are never deployed. Two clean builds must produce byte-identical copies of all six
JARs.

Publication retains exact signed-tag checkout, signature fingerprint and protected-
master reachability checks, Central immutability preflight, protected
`production-release` approval, eight detached signatures, automatic publication,
fresh remote verification, and GitHub Release creation.

## Final conversion and immutable tag

Final conversion changes together:

- core and processor project versions;
- reactor and travel-example versions; and
- `gse.version` in all three independent consumers.

Published compatibility coordinates, recorded artifact hashes, historical documents,
cloud baseline names, and release links must not be mechanically changed. The final
conversion also freezes `project.build.outputTimestamp` and changes the unreleased
changelog heading to `3.2.0 — <actual release date>`.

After the release-preparation PR merges, wait for exact-commit protected CI. The signed
tag must point to that resulting protected-master commit, not its feature-branch
predecessor. Verify the tag locally before pushing it. Maven Central coordinates and
pushed signed tags are immutable; a defect requires a new patch version, never an
overwrite.

## Required validation families

Snapshot and final candidates run the same families with the appropriate expected
version:

```bash
scripts/verify-version-alignment.sh <expected-version>
./mvnw -q clean verify
./mvnw -q -f reactor/pom.xml clean verify
./mvnw clean -Papi-compat test
./mvnw clean -Partifact-compat verify
./mvnw -Dmaven.repo.local=<fresh-dir> clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
scripts/run-travel-example.sh
./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify
scripts/verify-release-artifacts.sh <expected-version>
scripts/verify-reproducible-build.sh
./mvnw clean -Pjmh -DskipTests package
scripts/verify-jmh-smoke.sh
python3.11 -m unittest scripts.cloud.test_benchmark_v2 \
  scripts.cloud.test_benchmark_comparison_v2 \
  scripts.cloud.test_benchmark_upload_v2 \
  scripts.cloud.test_cloud_workflow_v2
git diff --check
```

Shell syntax and synthetic cloud lifecycle gates exercised by `CI / Required` remain
mandatory. Protected publication additionally builds with GPG enabled and verifies all
signatures. Local unsigned validation does not replace protected-workflow evidence.

The explicit `reduced-test` stabilization mode is CI pipeline evidence, not machine
stability evidence. It must enforce structural and safety readiness before exercising
measurement and measurement-only JFR, while treating short-window throughput and
latency stability flags as diagnostic. Production `screening`, `confirmation`, and
`profile` modes continue to require every frozen cross-window stability threshold.

## Completion boundary

Phase 6 is complete only after real post-publication evidence is recorded and merged.
Snapshot acceptance and final-candidate acceptance are intermediate states. Published
`3.2.0` then becomes a mandatory future compatibility baseline while every earlier
published baseline remains immutable.
