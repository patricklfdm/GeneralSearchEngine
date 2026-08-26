# V3 Phase 2 implementation checklist

## Preparation and frozen boundary

- [x] Phase 1 is merged to `master` with all Phase 1 gates passing.
- [x] Work starts from `feat/v3-phase2-positional-postings` at the merged Phase 1 commit.
- [x] Existing `PostingList`, `TextIndexBuilder`, `TextIndexSnapshot`, scan predicates,
  BM25 term analysis, dynamic-index replay, and compatibility descriptors are audited.
- [x] The canonical V3 phase order is recorded in
  [`docs/v3/ROADMAP.md`](../../ROADMAP.md).
- [x] Scope, activation, validation, storage, mutation, compatibility, performance, and
  non-goals are frozen in [POSITIONAL_STORAGE.md](POSITIONAL_STORAGE.md).
- [x] Root Codex prompt files remain local untracked implementation inputs.

## Positioned-analysis consistency

- [x] Apply the same frozen positioned-output validation/projection semantics across
  consumers, reusing internal code where package boundaries allow without adding a
  supported public validation API.
- [x] Reject a null result list, null element, invalid first increment, and logical
  position overflow with contextual `IllegalArgumentException`.
- [x] Propagate Analyzer-thrown exceptions unchanged.
- [x] Validate complete output before mutating builder state.
- [x] Migrate `TextIndexBuilder` document analysis to positioned output.
- [x] Migrate indexed and scan text-query term projection consistently.
- [x] Migrate `TextScoringQuery` term projection consistently.
- [x] Retain current distinct-term and encounter-order rules in term-only consumers.
- [x] Keep public `TextField.analyzeDocument(T)` and its legacy behavior unchanged.
- [x] Prove default-adapted legacy analyzers retain identical analyzed terms and results.

## `IntPositions`

- [x] Add package-private final `IntPositions` in the text-index package.
- [x] Use privately owned primitive backing storage.
- [x] Require non-negative, strictly increasing values.
- [x] Defensively copy caller-owned mutable input.
- [x] Expose package-private `size`, indexed access, and `contains` operations.
- [x] Implement deterministic value equality and hash code.
- [x] Support an immutable empty value without exposing an array.
- [x] Add no compression, boxing-per-occurrence, offsets, or public positional API.

## `PostingList` migration

- [x] Replace the private frequency map with `docId -> IntPositions`.
- [x] Derive `termFrequency(docId)` only from stored positions.
- [x] Keep bitmap and position-map membership consistent.
- [x] Preserve all existing public method and constructor descriptors.
- [x] Preserve current `withTermFrequency` argument validation.
- [x] Preserve same-frequency identity reuse in `withTermFrequency`.
- [x] Use sequential synthetic positions when legacy `withTermFrequency` changes a
  frequency.
- [x] Add package-private position-aware read/update operations.
- [x] Return immutable empty positions for an absent document.
- [x] Preserve `without` validation, absence no-op, membership, and frequency behavior.

## Position and document-length mapping

- [x] Start logical position at `-1` and add increments without integer wrap.
- [x] Retain initial and later gaps.
- [x] Retain different terms at the same position.
- [x] Retain repeated terms at every distinct logical position.
- [x] Deduplicate the same `(term, position)` pair.
- [x] Define term frequency as unique stored positions for that term and document.
- [x] Count every emitted token in document length, including a deduplicated positional
  duplicate.
- [x] Keep document length independent of maximum logical position.
- [x] Analyze each old or new document once per index operation.

## Mutation, publication, and lifecycle

- [x] Store analyzed state as value-equivalent positions-by-term plus token count.
- [x] Treat token reordering as a change even when every term frequency is unchanged.
- [x] Reuse state only when both positional maps and token count are equal.
- [x] Republish a term when positions change but position count does not.
- [x] Publish document-length-only changes even when positional maps are equal.
- [x] Remove positions, frequency visibility, and bitmap membership together.
- [x] Remove empty postings from the term dictionary.
- [x] Preserve old snapshot positions after later add/update/remove operations.
- [x] Preserve structural sharing for unchanged postings and length metadata.
- [x] Preserve atomic startup and normal mutation publication.
- [x] Preserve bulk add/update/remove rollback and single-publication behavior.
- [x] Preserve dynamic text-index build, mutation replay, drop/recreate, failure, and
  retry behavior.

## Focused and randomized tests

- [x] Cover `IntPositions` size, indexed access, contains, equality, hash code, empty,
  validation, defensive copying, and absence of array leakage.
- [x] Cover `very very good -> very:[0,1], good:[2]`.
- [x] Cover position gaps with token count independent of maximum position.
- [x] Cover same-position alternatives with different terms.
- [x] Cover a duplicate term at the same position and its TF-versus-length semantics.
- [x] Cover an initial gap and `Integer.MAX_VALUE` boundary/overflow.
- [x] Cover null list, null element, first increment zero, and analyzer exception
  behavior.
- [x] Cover order-sensitive update and complete-state no-op reuse.
- [x] Cover length-only update, removal cleanup, and snapshot isolation.
- [x] Cover unchanged TermQuery, AnyTermsQuery, and AllTermsQuery indexed/scan truth.
- [x] Cover unchanged BM25 scores and ordering for default-adapted analyzers.
- [x] Cover a V3-native positioned override consistently across index, scan, and BM25.
- [x] Cover startup, bulk, dynamic build/replay, failure atomicity, and retry behavior.
- [x] Add deterministic randomized differential coverage for membership, positions, TF,
  document length, total length, mutations, gaps, alternatives, and reorderings.

## Performance evidence

- [x] Add or extend a focused positional text-index JMH/equivalent baseline.
- [x] Record representative build/mutation throughput and allocation or retained-memory
  evidence.
- [x] Confirm primitive occurrence storage and absence of an obvious boxing/pathological
  regression.
- [x] Document results without claiming a universal speedup or implementing compression.

## Compatibility and scope audit

- [x] Frozen v1 source/reflection fixture passes.
- [x] Japicmp passes against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [x] v1-, v2-, and v3-style independent consumers pass.
- [x] Public API inspection confirms no public positions type or unintended descriptor.
- [x] `PostingList` public descriptors and observable term-frequency behavior remain
  compatible.
- [x] No phrase/fuzzy/bool/boost/cross-field/new-request/Explain execution is added.
- [x] No planner/executor, compression, trie, automaton, offset, or unrelated refactor is
  added.
- [x] `RankedSearcher`, `CandidatePlanner`, bitmaps, writer concurrency, and snapshot
  publication architecture are not redesigned.

## Documentation and full validation

- [x] Update `CHANGELOG.md` after implementation.
- [x] Record performance observations in the Phase 2 completion documentation.
- [x] Mark Phase 2 complete in the roadmap and V3 phase map only after every gate passes.
- [x] `git diff --check` passes.
- [x] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [x] `./mvnw -f reactor/pom.xml clean test` passes.
- [x] `scripts/run-travel-example.sh` passes with unchanged observable output.
- [x] `./mvnw clean -Papi-compat test` passes.
- [x] `./mvnw clean -Partifact-compat verify` passes in normal and isolated repositories.
- [x] `scripts/verify-consumer-projects.sh` passes.
- [x] Strict core and processor Javadocs pass.
- [x] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [x] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [x] `scripts/verify-reproducible-build.sh` passes.
- [x] No generated artifact, local repository, credential, IDE file, or local Codex
  prompt is tracked.

Phase 2 is complete only when the index retains correct positions, all current text
paths agree on positioned terms, and published legacy behavior remains unchanged for
default-adapted analyzers. Visible phrase or fuzzy execution is scope failure, not extra
progress.
