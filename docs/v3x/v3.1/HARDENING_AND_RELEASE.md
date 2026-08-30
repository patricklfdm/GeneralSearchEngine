# V3.1 Phase 8 hardening and release contract

## Boundary

Phase 8 freezes the completed V3.1 capability set and proves that it is correct,
compatible, documented, reproducible, and safely publishable as `3.1.0`. It is a
hardening and release-engineering phase, not a feature phase.

The only permitted production behavior change is a minimal fix for a demonstrated
release blocker. Such a fix requires a failing regression test, a narrow implementation
change, targeted validation, and then every applicable Phase 8 gate. New ranked query
shapes, public tuning controls, broad refactoring, and speculative optimization belong
to a later independently frozen contract.

## Entry state and version identity

Phase 8 starts from protected `master` after Phase 7 evidence review and immutable
registration of `v3.1.0-ranked-cloud`. The source tree still resolves to `3.0.0` at
entry. That identity was retained deliberately during Phases 1–7 so the candidate could
be checked against the published `3.0.0` artifact with a pinned, isolated Japicmp
baseline. It is not a claim that the modified source is the published 3.0.0 release.

Phase 8 uses four ordered states:

1. **Entry and contract freeze** — project identity remains `3.0.0`; only the Phase 8
   contract, checklist, and truthful roadmap state change.
2. **Snapshot hardening** — every current project and consumer coordinate changes
   atomically to `3.1.0-SNAPSHOT`; correctness, compatibility, consumers, Javadocs,
   artifacts, reproducibility, benchmark smoke, and documentation gates pass.
3. **Final release preparation** — all aligned current coordinates change atomically
   to `3.1.0`; release metadata and the dated changelog are frozen; every final-version
   gate passes and the approved state is merged to protected `master`.
4. **Post-publication verification** — the signed `v3.1.0` tag workflow succeeds;
   Maven Central, the clean published consumer, and the GitHub Release are verified;
   actual evidence is recorded in a documentation-only follow-up commit.

Evidence from a later state must not be marked during an earlier state. A green final
tree is release-ready, not released. Tag identity, Central publication, deployment
details, remote artifact resolution, and GitHub Release status remain `PENDING` until
they exist.

## Frozen V3.1 capability and API surface

V3.1 adds exactly two supported application API methods:

```java
SearchQueries.phrase(TextField<T> field, String text, int slop)
SearchQueries.BoolBuilder<T>.minimumShouldMatch(int value)
```

The existing two-argument phrase factory remains exact slop zero. BOOL requests that
do not set `minimumShouldMatch` retain V3.0 behavior. The persistent code-point fuzzy
trie is a semantics-preserving internal optimization; complete Unicode code-point OSA
expansion, matching, scoring, and ordering remain unchanged.

The supported V1, V2, and V3.0 APIs remain compatible. `Analyzer` remains a SAM and
`AnalyzedToken` remains unchanged. No query node, normalized node, plan, posting,
position, trie or vocabulary node, candidate bitmap, score state, snapshot handle, or
internal document ID becomes supported API.

The existing Javadoc-hidden `PhrasePositionAccess` and `FuzzyVocabularyAccess`
bridges may retain only the narrow additions already reviewed in
[API compatibility](API_COMPATIBILITY.md). They remain unsupported package-layout
bridges rather than application SPIs. No new bytecode-public bridge is allowed in
Phase 8.

Before version conversion, review the complete Japicmp additions and both supported
methods for names, generic descriptors, overload resolution, null-literal behavior,
validation timing, defaults, exception behavior, thread-safety claims, and strict
Javadocs. Accidental public implementation types must be reviewed independently of
Japicmp.

## Correctness and compatibility hardening

The focused, deterministic randomized, differential, lifecycle, mutation, concurrency,
and Explain tests from Phases 1–7 remain permanent release gates. Phase 8 adds a test
only when an audit finds a meaningful missing invariant or reproduces a blocker.

The final matrix must retain:

- phrase slop normalization, ordered-gap matching, repeated terms, alternatives,
  scoring, filtering, ordering, and exact-slop-zero equivalence;
- implicit and explicit BOOL minimums, duplicate SHOULD occurrences, zero-term and
  matched-zero-score children, nesting, scoring, ordering, and Explain equivalence;
- persistent fuzzy-trie versus full-vocabulary-scan exact differential equivalence;
- snapshot, mutation, bulk, dynamic-index replay/build/drop, concurrent readers,
  close, and failure-precedence behavior;
- unchanged structured search, V2 `searchTopK`, V3.0 defaults, and Search/Explain
  match-score equivalence.

Japicmp must compare the candidate with published `1.0.0`, `2.0.0`, `2.1.0`, and
`3.0.0`. The copied 3.0.0 JAR must match its pinned SHA-256. A fresh isolated Maven
repository remains mandatory so a local build can never substitute for a published
baseline. Independent V1-, V2-, and V3-style consumers and the processor-enabled travel
example must compile and run only through supported APIs.

## Performance evidence inheritance

Phase 7 already produced the required V3.1 release evidence:

- the unchanged regression lane is directly compared with `v3.0.0-cloud`;
- the distinct `ranked-v31` feature family is reviewed and registered immutably as
  `v3.1.0-ranked-cloud`;
- the 1M mixed concurrency, publication, dynamic-index, failure, and 30-minute soak
  evidence is reviewed.

Documentation-only changes and aligned Maven version metadata do not invalidate those
measurements. Before release, audit the diff from the reviewed evidence source through
the final candidate. Any production Java, benchmark implementation, preset, workload,
JVM/toolchain, evidence-identity, or configuration change that could affect the result
invalidates the affected inheritance and requires a new comparable run and review.

No additional paid cloud run is required merely to replace `3.0.0` development
coordinates with `3.1.0-SNAPSHOT` or `3.1.0`. A blocker fix is evaluated according to
its affected surface; performance-sensitive fixes require renewed evidence.

## Documentation and release-facing state

Snapshot hardening must finalize:

- a V3.1 newcomer and migration path while clearly identifying published `3.0.0` as
  current stable until publication;
- the architecture, ranked semantics, API compatibility, validation, Phase 7 evidence,
  hardening contract, and release checklist links;
- an independent V3 consumer and travel example covering phrase slop and
  `minimumShouldMatch` through supported APIs;
- `README.md`, `docs/README.md`, `docs/v3x/README.md`, both roadmaps, and `CHANGELOG.md`
  so they describe actual rather than anticipated state.

Frozen historical files under `docs/v3/` remain the record of published `3.0.0` and
are not rewritten as V3.1 documentation. During snapshot and final preparation, public
installation examples continue to use published `3.0.0`; local-development examples
may use the aligned candidate version with an explicit unreleased label. Only after
successful publication may root documentation identify `3.1.0` as current stable.

## Artifacts, reproducibility, CI, and publication

The existing protected release workflow is reused. It must retain exact signed-tag
checkout, signature and protected-master reachability checks, full reactor tests,
four-baseline compatibility, three independent consumers, travel execution, JMH smoke,
release packaging, artifact isolation, reproducibility, Central immutability preflight,
protected `production-release` approval, signing, automatic Central publication,
fresh remote verification, and GitHub Release creation.

Only `general-search-engine` and `general-search-engine-processor` are publishable. Each
must contain its POM plus main, sources, and strict Javadoc JARs, signatures, and
checksums. The core JAR must not contain an annotation-processor service entry; the
processor JAR must contain exactly the expected entry. Reactor, examples,
compatibility consumers, benchmarks, and validation fixtures are never deployed.

Reproducibility covers the six publishable JARs. The final conversion freezes
`project.build.outputTimestamp` to the accepted release date convention and runs the
reproducibility gate again.

## Version conversion and immutable tag

The snapshot conversion changes together:

- core and processor project versions;
- reactor and travel-example versions;
- the `gse.version` property in all three independent consumers.

Published compatibility baselines `1.0.0`, `2.0.0`, `2.1.0`, and `3.0.0`, historical
consumer fixture identities, historical documentation, cloud baseline names, and
Central links must not be mechanically changed.

Do not convert to final `3.1.0` until every snapshot gate and the API, documentation,
and evidence-inheritance reviews are accepted. Convert all current coordinates
together, freeze the dated changelog and release metadata, and run every final gate
before the release-preparation PR is approved.

After that PR is merged, wait for protected `master` CI. The annotated signed
`v3.1.0` tag must point to that exact resulting `master` commit. If GitHub creates a
merge or squash commit, the protected-branch result—not its feature-branch
predecessor—is the tag target. Verify the tag locally before pushing it; the tag push
is the release trigger.

Maven Central coordinates and pushed signed tags are immutable. A source or metadata
defect before publication requires a reviewed commit and a new patch version. A release
infrastructure failure before upload may use the existing manual recovery dispatch for
the same exact tag. Tagged source may not change. A defect after publication requires
`3.1.1` or later and never an overwrite of `3.1.0`.

## Required validation families

Repository scripts and protected workflows are the source of truth. Snapshot and final
preparation both require the following with the appropriate expected version:

```bash
scripts/verify-version-alignment.sh <expected-version>
./mvnw -f reactor/pom.xml clean test
./mvnw -Pjmh -Dtest=V3ProductionSoakTest test
scripts/test-v3-soak-stabilization-e2e.sh
scripts/run-travel-example.sh
./mvnw clean -Papi-compat test
./mvnw clean -Partifact-compat verify
./mvnw -Dmaven.repo.local=<fresh-dir> clean -Partifact-compat verify
scripts/verify-consumer-projects.sh
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

Shell syntax and the synthetic cloud lifecycle tests exercised by `CI / Required` also
remain mandatory. The protected publication job additionally builds with GPG enabled
and requires all eight detached signatures. Local signing is useful when the key is
available but does not replace protected-workflow evidence.

## Completion boundary

Phase 8 is complete only after the post-publication evidence is real and recorded.
Release preparation can be declared ready before tagging, but not released. A
documentation-only follow-up records the exact tag/master commit, signing fingerprint,
workflow result, publication information exposed by Central, clean remote resolution,
published-consumer result, GitHub Release URL/time, and stable-version state.

Published `3.1.0` is then added as a mandatory compatibility baseline for subsequent
V3.x development while every older baseline remains. V3.2 starts only from its own
Phase 0 contract and never as an extension of Phase 8.

