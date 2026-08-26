# V3 Phase 8 hardening and release contract

## Boundary

Phase 8 freezes the implemented V3.0 capability set and proves that it is correct,
compatible, measurable, documented, reproducible, and safely publishable as 3.0.0.
It is a validation and release-engineering phase, not a feature phase.

The only permitted production behavior change is a minimal fix for a demonstrated
release blocker. Such a fix requires a failing regression test, a narrow implementation
change, targeted validation, and then every applicable Phase 8 gate. Optional
optimization, cleanup, or a new query capability is not a blocker fix.

## Repository truth

Phase 8 starts from `3.0.0-SNAPSHOT` after Phase 7 is merged to `master`. The existing
repository establishes these release mechanics:

- pull requests and `master` pushes run reactor, compatibility, consumer, packaging,
  artifact-integrity, reproducibility, and aggregate `CI / Required` gates;
- compatibility compares the core artifact with published 1.0.0, 2.0.0, and 2.1.0;
- v1-, v2-, and v3-style consumers are independent Maven modules;
- only `general-search-engine` and `general-search-engine-processor` are publishable;
- a signed `vMAJOR.MINOR.PATCH` tag reachable from `origin/master` triggers release;
- publication requires the protected `production-release` environment;
- the release workflow signs artifacts, publishes automatically to Central, waits for
  publication, resolves both coordinates, and creates the GitHub Release.

The V2.1 release checklist is a structural precedent, not the current deployment
procedure. Its manual Central Portal steps must not replace the automated tag workflow.

## Frozen capability and compatibility surface

The supported V3 additions are `AnalyzedToken`, the default
`Analyzer.analyzeWithPositions` method, `SearchRequest`, `SearchQuery`,
`SearchQueries`, `SearchResult`, `SearchExplanation`, `ExplanationNode`, and the
additive default `SearchEngine.search(SearchRequest)` and `SearchEngine.explain`
methods. `SnapshotSearchEngine` provides the built-in concrete implementations.

Existing structured `search(Query)` and V2 `searchTopK(RankedSearchRequest)` behavior
remain supported. Compatibility is required against 1.0.0, 2.0.0, and 2.1.0 for the
published application surface.

`SearchExecutionAccess`, `PhrasePositionAccess`, and `FuzzyVocabularyAccess` are
Javadoc-hidden bytecode-public package bridges forced by the current package layout.
They remain explicitly unsupported and may not expand beyond the exact boundaries
already recorded in `docs/v3/API_COMPATIBILITY.md`. Phase 8 must distinguish those
reviewed bridges from accidental public application API instead of assuming every
bytecode-public class is supported.

No query-node subtype, plan, posting, vocabulary, position, candidate bitmap, score
state, snapshot handle, or internal document ID becomes application API.

## Evidence states

Phase 8 uses three ordered states:

1. **Snapshot hardening** — version is `3.0.0-SNAPSHOT`; tests, compatibility,
   benchmarks, API review, docs, examples, and release automation are completed.
2. **Final release preparation** — aligned version is `3.0.0`; the changelog and
   release metadata are frozen; all final-version gates pass; the approved state is
   merged to protected `master`.
3. **Post-publication verification** — the signed tag workflow succeeds; Central and
   GitHub are verified through clean clients; actual release evidence is recorded in a
   follow-up commit.

Evidence from a later state must never be marked during an earlier state. In
particular, deployment ID, published resolution, GitHub Release status, and 3.0.0
current-stable status remain `PENDING` until publication actually succeeds.

## Public API freeze review

Before version conversion, review the complete Japicmp additions and every newly
supported V3 type for names, generic descriptors, null behavior, immutability, default
values, factories/constructors, exception timing, thread-safety claims, and strict
Javadocs. Search for accidental public implementation types independently of Japicmp.

Visibility may be reduced before publication only when the type is not frozen or
supported, source use is absent, bridge policy is preserved, and normal plus isolated
compatibility gates pass. Do not rename or reshape a frozen supported API under the
label of cleanup.

## Correctness hardening rule

The Phase 3–7 focused, randomized, and differential tests remain permanent. Add a test
only when an audit identifies a meaningful missing invariant or a blocker is reproduced.
Randomized tests use explicit deterministic seeds and remain bounded for CI.

The release matrix must retain coverage for structured filters, TEXT, recursive BOOL,
BOOST, cross-field BM25, exact phrase positions, fuzzy AUTO/OSA/expansion/scoring,
Explain equivalence, legacy ranked equivalence, snapshot isolation, mutation, bulk
atomicity, concurrent readers, and dynamic-index build/replay/drop behavior.

Stress cases are correctness tests with bounded data and time; they are not JMH
benchmarks. JMH results are evidence, not assertions in the unit-test suite.

## Performance and memory evidence

Measure before optimizing. Build a named representative JMH matrix that covers:

- V2-equivalent text, text plus structured filter, and normal V3 text;
- MUST, SHOULD-only, nested BOOL, BOOST, and cross-field composition;
- selective/common/repeated/gapped exact phrases;
- fuzzy exact, edit, transposition, no-match, and high-expansion cases;
- normal search versus matching/non-matching Explain;
- positional add/update/remove and bulk mutation behavior.

For fuzzy vocabulary scaling, 10k and 100k rows are required. Run a bounded 1M capacity
row when the target machine can do so without swapping or invalid measurement; otherwise
record the exact resource limitation. Query lengths and edit shapes form a representative
named set, not an unbounded Cartesian product.

Record JDK, JVM flags, hardware, forks, warmup, measurement, corpus shape, benchmark
selection, raw-result location, summarized results, and limitations. Raw generated
results stay under `target/`; only reviewed summaries belong in documentation.

Memory evidence must quantify representative term occurrences, positional primitive
storage, posting/dictionary metadata, document lengths, and bitmap storage without
claiming a universal heap ratio. A documented measurement or transparent estimate is
acceptable if its method and limitations are reproducible.

No arbitrary pass/fail threshold is invented after seeing results. A material
V2-equivalent regression or severe new-feature pathology is investigated. New-feature
absolute costs and accepted tradeoffs are documented.

The default decisions are to retain bounded complete vocabulary scan and raw immutable
primitive positions for 3.0.0. Changing either requires release-blocking evidence, a
semantics-preserving internal fix, and rerunning every correctness/compatibility gate.
No hidden expansion cap, public tuning knob, phrase slop, or position opt-out may appear.

## Documentation and example contract

Snapshot hardening produces or finalizes:

- root `README.md` with a concise V3 newcomer path while 2.1.0 remains identified as
  the currently published stable release;
- `docs/v3/MIGRATION_GUIDE.md` describing optional 2.1-to-3.0 adoption;
- `docs/v3/API_COMPATIBILITY.md` and the frozen semantic documents;
- `docs/v3/PERFORMANCE_BASELINE.md` with measured evidence and decision gates;
- `docs/v3/RELEASE_CHECKLIST.md` with evidence-state-aware release tracking;
- `docs/README.md`, `docs/v3/README.md`, roadmap, and changelog links;
- the reactor-built travel example demonstrating structured search, V3 ranked text,
  cross-field BOOL/BOOST, phrase, fuzzy, filter, Explain, and dynamic-index lifecycle.

The travel example stays realistic and compact. It must use only supported public APIs
and execute in CI. Internal planning concepts do not belong in the newcomer flow.

During final conversion, dependency coordinates and release-facing version references
become 3.0.0, but publication evidence is not claimed. Only after successful publication
may a follow-up commit identify 3.0.0 as the current published stable version.

## CI and release automation contract

`CI / Required` must depend on every release-critical CI job. Full performance runs are
manual evidence and do not belong in the per-PR required gate; JMH source compilation or
a bounded smoke check may be required if inexpensive.

The release workflow must preserve tag validation, signature verification, full tests,
three-baseline compatibility, three consumers, travel execution, release packaging,
artifact isolation, reproducibility, Central immutability preflight, protected approval,
GPG signing, automatic Central publication, and GitHub Release creation.

Post-publication checks must use a fresh isolated Maven repository that contains no
locally installed 3.0.0 build. They must fetch both publishable coordinates and verify
the POM, main/sources/Javadoc artifacts, detached signatures, and checksums. At least
one representative V3 consumer must compile and run in a mode that does not install the
reactor first. Reusable scripts are preferred over workflow-only shell fragments.

The core JAR must contain no processor service entry. The processor JAR must contain
exactly the expected processor service entry. Reactor, example, compatibility,
benchmark, and validation modules must never be deployed.

## Version conversion and tag contract

Do not change to 3.0.0 until all snapshot gates and the performance/API/doc reviews are
accepted. Convert core, processor, reactor, example, and all current-version consumer
properties together; historical published baselines remain unchanged. Freeze the
output timestamp according to the existing reproducible-build convention and finalize
the dated changelog heading.

Run every final-version gate before opening the final release-preparation PR. After the
PR is approved, merge it to protected `master` and wait for required CI. The signed
`v3.0.0` tag must point to that exact resulting `master` commit. If GitHub created a
merge or squash commit, that protected-branch result—not the feature-branch predecessor—is
the tag target.

Verify the local signed tag before pushing. The push triggers the established workflow;
do not run a separate manual deploy. Maven Central versions and pushed signed release
tags are immutable. A source or metadata defect before publication requires a new
reviewed commit and patch version. If only release infrastructure fails before secrets
or upload, a reviewed workflow recovery may dispatch the same exact tag through the
same validation, Central preflight, protected approval, signing, publication, and
remote-verification jobs. The recovery must not alter tagged source. A defect after
publication requires 3.0.1 or later and never an overwrite of 3.0.0.

## Release record boundary

Before tagging, the release checklist records test counts, compatibility reports,
consumer/example results, artifact inspection, reproducibility, and final hashes that
are already known. Tag verification, deployment ID, clean Central resolution, remote
signature/checksum verification, published consumer result, and GitHub Release remain
`PENDING`.

After publication, a documentation-only follow-up commit records the actual tag commit,
fingerprint, workflow result, deployment information exposed by the workflow/Central,
remote resolution results, GitHub Release URL/time, and final stable-version state.
This follow-up is intentionally outside the immutable signed tag.

Adding published 3.0.0 as a future compatibility baseline is also post-publication work;
older 1.0.0, 2.0.0, and 2.1.0 baselines remain.

## Required validation families

Use the repository scripts as the source of truth. Snapshot and final preparation both
require, with the appropriate expected version:

```bash
scripts/verify-version-alignment.sh <expected-version>
./mvnw -f reactor/pom.xml clean test
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
git diff --check
```

The protected release job additionally builds with GPG enabled and runs
`scripts/verify-release-artifacts.sh --require-signatures 3.0.0`. A local signed build
is useful when the key is available but does not replace protected-workflow evidence.

## Explicit non-goals

Phase 8 does not add query features, scoring models, public tuning knobs, plan/cache
architecture, persistence, vector retrieval, or distributed execution. It does not
perform broad refactoring or speculative optimization. It does not commit root Codex
prompts, credentials, signatures, raw benchmark dumps, target directories, local Maven
repositories, or IDE metadata.

Phase 8 is complete only after the post-publication evidence is real and recorded. A
green pre-tag tree means release-ready, not released.
