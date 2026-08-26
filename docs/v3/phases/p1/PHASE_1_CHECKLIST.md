# V3 Phase 1 implementation checklist

## Preparation

- [x] Phase 0 is merged to `master` and all Phase 0 gates passed.
- [x] Work starts from `feat/v3-phase1-positions` based on the merged Phase 0 commit.
- [x] The Phase 0 positional contract has been reviewed without changing its meaning.
- [x] Existing Analyzer, Token, SimpleAnalyzer, TextField, query, index, and ranking call
  sites have been audited.
- [x] The Phase 1 scope and non-goals are frozen in
  [POSITION_AWARE_ANALYSIS.md](POSITION_AWARE_ANALYSIS.md).
- [x] The local `V3_Phase0_Codex_Prompt.md` remains an untracked implementation input.

## Public API implementation

- [ ] Add public `AnalyzedToken(String term, int positionIncrement)` in the analysis
  package.
- [ ] Preserve record-component order: `term`, then `positionIncrement`.
- [ ] Reject null/empty terms and negative increments with `IllegalArgumentException`.
- [ ] Accept increment zero and positive increments at the record boundary.
- [ ] Add `Analyzer.analyzeWithPositions(String)` as a default method.
- [ ] Keep `Analyzer` annotated with `@FunctionalInterface` and retain one abstract
  method.
- [ ] Implement the exact one-call, encounter-order, duplicate-preserving, all-ones
  adapter.
- [ ] Return an unmodifiable positional-token list.
- [ ] Add strict Javadocs for the new record, components, constructor behavior, method,
  parameter, return value, and failures.

## Contract tests

- [ ] `AnalyzedToken` accepts zero, one, and large positive increments.
- [ ] `AnalyzedToken` rejects null term, empty term, and negative increment.
- [ ] Record reflection confirms the frozen component names, order, and types.
- [ ] A legacy Analyzer lambda still compiles and executes.
- [ ] The default adapter invokes legacy analysis exactly once.
- [ ] The default adapter passes the original input reference, including null.
- [ ] Encounter order, duplicate terms, exact strings, and increment one are preserved.
- [ ] Empty analysis returns an empty positional list.
- [ ] The returned list is unmodifiable.
- [ ] Legacy analyzer exceptions propagate unchanged.
- [ ] A custom `analyzeWithPositions` override can emit gaps and same-position
  alternatives without affecting `analyze`.
- [ ] `Analyzer.simple()` positional terms exactly project its existing Token terms.
- [ ] Existing SimpleAnalyzer Unicode, normalization, concurrency, and Token tests remain
  unchanged and green.

## Compatibility and consumer gates

- [ ] The v3 consumer compiles direct `AnalyzedToken` construction.
- [ ] The v3 consumer compiles `analyzeWithPositions` on a legacy lambda Analyzer.
- [ ] The frozen v1 source/reflection fixture passes.
- [ ] Japicmp passes against published 1.0.0, 2.0.0, and 2.1.0 from an isolated Maven
  repository.
- [ ] v1-, v2-, and v3-style independent consumers pass.
- [ ] Public API inspection confirms no additional Analyzer abstract method or unintended
  public type.

## Regression boundary

- [ ] No production call site outside `Analyzer` invokes `analyzeWithPositions`.
- [ ] `Token` and its JVM record descriptor are unchanged.
- [ ] `SimpleAnalyzer.analyze` output is unchanged.
- [ ] Existing boolean text truth and result order are unchanged.
- [ ] Existing term frequency, document length, BM25 scores, and ranking order are
  unchanged.
- [ ] No text index, posting, snapshot, mutation, or lifecycle implementation changes.
- [ ] No positional storage, phrase/fuzzy execution, planner/executor, or Explain
  execution is introduced.

## Documentation and full validation

- [ ] Update `CHANGELOG.md` after the API implementation lands.
- [ ] Mark Phase 1 complete in `docs/v3/README.md` only after every gate passes.
- [ ] `git diff --check` passes.
- [ ] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [ ] `./mvnw -f reactor/pom.xml clean test` passes.
- [ ] `scripts/run-travel-example.sh` passes with unchanged observable output.
- [ ] `./mvnw clean -Papi-compat test` passes.
- [ ] `./mvnw clean -Partifact-compat verify` passes in the normal local repository.
- [ ] The same artifact compatibility gate passes from an isolated Maven repository.
- [ ] `scripts/verify-consumer-projects.sh` passes.
- [ ] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [ ] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [ ] `scripts/verify-reproducible-build.sh` passes.
- [ ] No generated artifact, local repository, credential, or IDE file is tracked.

Phase 1 is complete only when the additive API is independently usable and all legacy
text behavior remains unchanged. Positional storage or phrase execution is evidence of
scope failure, not extra progress.
