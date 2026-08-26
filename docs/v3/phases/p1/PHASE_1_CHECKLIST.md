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

- [x] Add public `AnalyzedToken(String term, int positionIncrement)` in the analysis
  package.
- [x] Preserve record-component order: `term`, then `positionIncrement`.
- [x] Reject null/empty terms and negative increments with `IllegalArgumentException`.
- [x] Accept increment zero and positive increments at the record boundary.
- [x] Add `Analyzer.analyzeWithPositions(String)` as a default method.
- [x] Keep `Analyzer` annotated with `@FunctionalInterface` and retain one abstract
  method.
- [x] Implement the exact one-call, encounter-order, duplicate-preserving, all-ones
  adapter.
- [x] Return an unmodifiable positional-token list.
- [x] Add strict Javadocs for the new record, components, constructor behavior, method,
  parameter, return value, and failures.

## Contract tests

- [x] `AnalyzedToken` accepts zero, one, and large positive increments.
- [x] `AnalyzedToken` rejects null term, empty term, and negative increment.
- [x] Record reflection confirms the frozen component names, order, and types.
- [x] A legacy Analyzer lambda still compiles and executes.
- [x] The default adapter invokes legacy analysis exactly once.
- [x] The default adapter passes the original input reference, including null.
- [x] Encounter order, duplicate terms, exact strings, and increment one are preserved.
- [x] Empty analysis returns an empty positional list.
- [x] The returned list is unmodifiable.
- [x] Legacy analyzer exceptions propagate unchanged.
- [x] A custom `analyzeWithPositions` override can emit gaps and same-position
  alternatives without affecting `analyze`.
- [x] `Analyzer.simple()` positional terms exactly project its existing Token terms.
- [x] Existing SimpleAnalyzer Unicode, normalization, concurrency, and Token tests remain
  unchanged and green.

## Compatibility and consumer gates

- [x] The v3 consumer compiles direct `AnalyzedToken` construction.
- [x] The v3 consumer compiles `analyzeWithPositions` on a legacy lambda Analyzer.
- [x] The frozen v1 source/reflection fixture passes.
- [x] Japicmp passes against published 1.0.0, 2.0.0, and 2.1.0 from an isolated Maven
  repository.
- [x] v1-, v2-, and v3-style independent consumers pass.
- [x] Public API inspection confirms no additional Analyzer abstract method or unintended
  public type.

## Regression boundary

- [x] No production call site outside `Analyzer` invokes `analyzeWithPositions`.
- [x] `Token` and its JVM record descriptor are unchanged.
- [x] `SimpleAnalyzer.analyze` output is unchanged.
- [x] Existing boolean text truth and result order are unchanged.
- [x] Existing term frequency, document length, BM25 scores, and ranking order are
  unchanged.
- [x] No text index, posting, snapshot, mutation, or lifecycle implementation changes.
- [x] No positional storage, phrase/fuzzy execution, planner/executor, or Explain
  execution is introduced.

## Documentation and full validation

- [x] Update `CHANGELOG.md` after the API implementation lands.
- [x] Mark Phase 1 complete in `docs/v3/README.md` only after every gate passes.
- [x] `git diff --check` passes.
- [x] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [x] `./mvnw -f reactor/pom.xml clean test` passes.
- [x] `scripts/run-travel-example.sh` passes with unchanged observable output.
- [x] `./mvnw clean -Papi-compat test` passes.
- [x] `./mvnw clean -Partifact-compat verify` passes in the normal local repository.
- [x] The same artifact compatibility gate passes from an isolated Maven repository.
- [x] `scripts/verify-consumer-projects.sh` passes.
- [x] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [x] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [x] `scripts/verify-reproducible-build.sh` passes.
- [x] No generated artifact, local repository, credential, or IDE file is tracked.

Phase 1 is complete only when the additive API is independently usable and all legacy
text behavior remains unchanged. Positional storage or phrase execution is evidence of
scope failure, not extra progress.
