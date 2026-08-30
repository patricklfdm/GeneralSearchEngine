# V3.1 Phase 8 hardening and release checklist

Status: entry audit and contract freeze complete; snapshot conversion has not started.

## Entry and frozen boundary

- [x] Phase 7 implementation and evidence reviews are merged to protected `master`.
- [x] The frozen regression comparison remains directly comparable with
  `v3.0.0-cloud`.
- [x] The distinct ranked feature family is registered immutably as
  `v3.1.0-ranked-cloud`.
- [x] Existing V3.0 hardening/release precedent, CI, release workflow, scripts,
  consumers, artifact rules, and reproducibility rules are audited.
- [x] The four Phase 8 evidence states and permitted blocker-fix boundary are frozen in
  [the hardening and release contract](HARDENING_AND_RELEASE.md).
- [x] Entry project identity remains `3.0.0`; no release or publication claim is made.
- [ ] Work continues on an independent `feat/v3.1-phase8-hardening-release` branch.
- [ ] No Phase 8 change introduces a V3.2 feature, ranked `mustNot`, public fuzzy
  controls, broad refactoring, or speculative optimization.

## Snapshot identity — `3.1.0-SNAPSHOT`

- [ ] Change core, processor, reactor, travel example, and all current consumer
  properties atomically to `3.1.0-SNAPSHOT`.
- [ ] Preserve published compatibility versions, historical fixture identities,
  frozen `docs/v3/` records, and cloud baseline names.
- [ ] Add an unreleased V3.1 changelog section without claiming publication.
- [ ] Keep root installation guidance on published `3.0.0` until publication.
- [ ] `scripts/verify-version-alignment.sh 3.1.0-SNAPSHOT` passes.

## Public API freeze

- [ ] Review the complete Japicmp additions against `1.0.0`, `2.0.0`, `2.1.0`, and
  `3.0.0`.
- [ ] Confirm the only supported additions are the phrase-slop factory and
  `BoolBuilder.minimumShouldMatch(int)`.
- [ ] Review generic descriptors, overload and null-literal behavior, validation and
  exception timing, defaults, immutability, and strict Javadocs.
- [ ] Confirm `Analyzer` remains a SAM and `AnalyzedToken` remains unchanged.
- [ ] Confirm no accidental implementation type or new bytecode-public bridge is
  introduced.
- [ ] Confirm `PhrasePositionAccess` and `FuzzyVocabularyAccess` remain narrow,
  Javadoc-hidden, unsupported bridges.
- [ ] Update [API compatibility](API_COMPATIBILITY.md) with the final accepted diff.

## Correctness hardening

- [ ] Audit phrase slop, BOOL minimum, fuzzy-trie equivalence, Explain, structured and
  V2/V3.0 default behavior, mutation, snapshot, lifecycle, and concurrency coverage.
- [ ] Preserve all focused and deterministic randomized/differential suites from
  Phases 1–7.
- [ ] Add only tests that close a named release-critical gap.
- [ ] Require a failing regression test and minimal fix for every discovered blocker.
- [ ] Confirm Search and Explain retain identical match and score semantics.
- [ ] Confirm exact phrase, unspecified BOOL, and fuzzy behavior remain
  V3.0-compatible.
- [ ] Confirm snapshot, bulk mutation, dynamic index, concurrent publication, close,
  and failure-precedence invariants.
- [ ] Close the remaining implementation-exit items in `PHASE_0_CHECKLIST.md` only
  when their evidence is revalidated.

## Compatibility, consumers, and example

- [ ] Frozen V1 source/reflection fixture passes.
- [ ] Japicmp passes against published `1.0.0`, `2.0.0`, `2.1.0`, and pinned
  `3.0.0`.
- [ ] Normal and fresh-isolated artifact compatibility runs both pass.
- [ ] V1-style consumer passes unchanged.
- [ ] V2-style consumer and optional processor path pass unchanged.
- [ ] V3-style consumer covers phrase slop and `minimumShouldMatch` through supported
  APIs.
- [ ] Reactor-built travel example compiles and runs through supported APIs.

## Phase 7 performance evidence inheritance

- [ ] Audit the diff from both reviewed Phase 7 evidence sources to the release
  candidate.
- [ ] Confirm no production, benchmark, preset, workload, JVM/toolchain,
  configuration, or evidence-identity change invalidates the frozen regression lane.
- [ ] Confirm the ranked feature family remains separate from the V3.0 regression
  family.
- [ ] Record that Maven version metadata and documentation-only changes do not require
  another paid cloud run.
- [ ] If an affecting blocker fix lands, rerun and review the applicable local or cloud
  evidence before release.
- [ ] JMH source packaging and the bounded forked smoke pass on the final candidate.

## Documentation

- [ ] Root README explains the V3.1 additions and unreleased status without changing
  the current stable dependency prematurely.
- [ ] V3.1 newcomer/migration guidance covers phrase slop, BOOL minimum, defaults, and
  compatibility.
- [ ] Architecture, semantics, compatibility, validation, evidence, hardening, and
  checklist documents agree with the final implementation.
- [ ] `docs/README.md` and `docs/v3x/README.md` link all final V3.1 documents.
- [ ] `docs/v3x/ROADMAP.md`, `DEVELOPMENT_ROADMAP.md`, and `CHANGELOG.md` describe
  actual rather than anticipated state.
- [ ] Frozen V3.0 historical documents remain unchanged except for an explicitly
  justified cross-version link, if needed.
- [ ] A state-aware V3.1 release record exists with pre-tag and post-publication
  sections.

## CI, artifacts, and reproducibility

- [ ] `CI / Required` still depends on reactor, compatibility, release-artifact, and
  cloud-runner jobs.
- [ ] Java 21 and Python 3.11 workflow assumptions remain explicit and valid.
- [ ] Strict release Javadocs pass for core and processor.
- [ ] Only core and processor are publishable.
- [ ] Core has no processor service entry; processor has exactly the expected entry.
- [ ] Main, sources, and Javadoc JARs exist for both published artifacts.
- [ ] Two clean builds produce byte-identical six-JAR output.
- [ ] Central immutability preflight and protected `production-release` approval remain
  mandatory.
- [ ] Tag validation still requires an annotated signed tag reachable from
  `origin/master`.
- [ ] Remote verification still uses a fresh Maven repository and checks POMs, JARs,
  signatures, checksums, manifests, service entries, and a clean published consumer.

## Snapshot validation — `3.1.0-SNAPSHOT`

- [ ] `git diff --check` passes.
- [ ] Version alignment passes.
- [ ] Full reactor tests pass; record core and processor test counts.
- [ ] Benchmark instrumentation and reduced stabilization E2E tests pass.
- [ ] Travel example passes.
- [ ] Frozen API fixture passes.
- [ ] Normal and fresh-isolated four-baseline Japicmp pass.
- [ ] All independent consumers pass.
- [ ] Unsigned release packaging and artifact inspection pass.
- [ ] Reproducible-build verification passes; record six hashes.
- [ ] JMH package and forked smoke pass.
- [ ] Python 3.11 Cloud Benchmark unit suite, shell syntax, and synthetic lifecycle
  gates pass.
- [ ] Protected PR/master `CI / Required` passes for the accepted snapshot state.

## Final version conversion — `3.1.0`

- [ ] Every snapshot hardening, API, documentation, and evidence-inheritance item is
  accepted before conversion.
- [ ] Convert all current project and consumer coordinates together to `3.1.0`.
- [ ] Preserve all published compatibility and cloud baseline identities.
- [ ] Freeze `project.build.outputTimestamp` according to the accepted release-date
  convention.
- [ ] Convert the changelog heading to `3.1.0 — <actual release date>`.
- [ ] Remove release-facing `3.1.0-SNAPSHOT` references while preserving historical
  evidence where appropriate.
- [ ] Repeat every snapshot validation family against `3.1.0`.
- [ ] Record final artifact hashes and pre-tag evidence in the release record.
- [ ] Merge the approved release-preparation PR to protected `master` and wait for
  required CI.

## Signed tag and publication — initially `PENDING`

- [ ] Create annotated signed `v3.1.0` on the exact approved protected-`master` commit.
- [ ] Verify tag type, signature fingerprint, version alignment, changelog heading,
  HEAD identity, and `origin/master` reachability locally.
- [ ] Push only the verified tag and let the protected Release workflow run.
- [ ] Release validation and Central immutability preflight pass.
- [ ] Approve the `production-release` environment after validation.
- [ ] Core and processor publish successfully to Maven Central with all required
  signed artifacts.
- [ ] Clean remote verification and published V3 consumer pass without a local reactor
  install.
- [ ] GitHub Release is created from the exact verified tag and marked latest.

## Post-publication record — initially `PENDING`

- [ ] Record exact tag/master commit, signing fingerprint, workflow run, publication
  information, remote verification, and GitHub Release URL/time.
- [ ] Update root and V3.x documentation to identify `3.1.0` as current stable.
- [ ] Add published `3.1.0` as a mandatory future compatibility baseline while
  retaining `1.0.0`, `2.0.0`, `2.1.0`, and `3.0.0`.
- [ ] Treat published `3.1.0` and signed `v3.1.0` as immutable; later fixes use a new
  version.
- [ ] Mark Phase 8 and V3.1 complete only after the evidence commit is merged.

