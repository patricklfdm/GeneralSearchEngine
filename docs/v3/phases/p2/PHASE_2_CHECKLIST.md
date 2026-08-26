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

- [ ] Apply the same frozen positioned-output validation/projection semantics across
  consumers, reusing internal code where package boundaries allow without adding a
  supported public validation API.
- [ ] Reject a null result list, null element, invalid first increment, and logical
  position overflow with contextual `IllegalArgumentException`.
- [ ] Propagate Analyzer-thrown exceptions unchanged.
- [ ] Validate complete output before mutating builder state.
- [ ] Migrate `TextIndexBuilder` document analysis to positioned output.
- [ ] Migrate indexed and scan text-query term projection consistently.
- [ ] Migrate `TextScoringQuery` term projection consistently.
- [ ] Retain current distinct-term and encounter-order rules in term-only consumers.
- [ ] Keep public `TextField.analyzeDocument(T)` and its legacy behavior unchanged.
- [ ] Prove default-adapted legacy analyzers retain identical analyzed terms and results.

## `IntPositions`

- [ ] Add package-private final `IntPositions` in the text-index package.
- [ ] Use privately owned primitive backing storage.
- [ ] Require non-negative, strictly increasing values.
- [ ] Defensively copy caller-owned mutable input.
- [ ] Expose package-private `size`, indexed access, and `contains` operations.
- [ ] Implement deterministic value equality and hash code.
- [ ] Support an immutable empty value without exposing an array.
- [ ] Add no compression, boxing-per-occurrence, offsets, or public positional API.

## `PostingList` migration

- [ ] Replace the private frequency map with `docId -> IntPositions`.
- [ ] Derive `termFrequency(docId)` only from stored positions.
- [ ] Keep bitmap and position-map membership consistent.
- [ ] Preserve all existing public method and constructor descriptors.
- [ ] Preserve current `withTermFrequency` argument validation.
- [ ] Preserve same-frequency identity reuse in `withTermFrequency`.
- [ ] Use sequential synthetic positions when legacy `withTermFrequency` changes a
  frequency.
- [ ] Add package-private position-aware read/update operations.
- [ ] Return immutable empty positions for an absent document.
- [ ] Preserve `without` validation, absence no-op, membership, and frequency behavior.

## Position and document-length mapping

- [ ] Start logical position at `-1` and add increments without integer wrap.
- [ ] Retain initial and later gaps.
- [ ] Retain different terms at the same position.
- [ ] Retain repeated terms at every distinct logical position.
- [ ] Deduplicate the same `(term, position)` pair.
- [ ] Define term frequency as unique stored positions for that term and document.
- [ ] Count every emitted token in document length, including a deduplicated positional
  duplicate.
- [ ] Keep document length independent of maximum logical position.
- [ ] Analyze each old or new document once per index operation.

## Mutation, publication, and lifecycle

- [ ] Store analyzed state as value-equivalent positions-by-term plus token count.
- [ ] Treat token reordering as a change even when every term frequency is unchanged.
- [ ] Reuse state only when both positional maps and token count are equal.
- [ ] Republish a term when positions change but position count does not.
- [ ] Publish document-length-only changes even when positional maps are equal.
- [ ] Remove positions, frequency visibility, and bitmap membership together.
- [ ] Remove empty postings from the term dictionary.
- [ ] Preserve old snapshot positions after later add/update/remove operations.
- [ ] Preserve structural sharing for unchanged postings and length metadata.
- [ ] Preserve atomic startup and normal mutation publication.
- [ ] Preserve bulk add/update/remove rollback and single-publication behavior.
- [ ] Preserve dynamic text-index build, mutation replay, drop/recreate, failure, and
  retry behavior.

## Focused and randomized tests

- [ ] Cover `IntPositions` size, indexed access, contains, equality, hash code, empty,
  validation, defensive copying, and absence of array leakage.
- [ ] Cover `very very good -> very:[0,1], good:[2]`.
- [ ] Cover position gaps with token count independent of maximum position.
- [ ] Cover same-position alternatives with different terms.
- [ ] Cover a duplicate term at the same position and its TF-versus-length semantics.
- [ ] Cover an initial gap and `Integer.MAX_VALUE` boundary/overflow.
- [ ] Cover null list, null element, first increment zero, and analyzer exception
  behavior.
- [ ] Cover order-sensitive update and complete-state no-op reuse.
- [ ] Cover length-only update, removal cleanup, and snapshot isolation.
- [ ] Cover unchanged TermQuery, AnyTermsQuery, and AllTermsQuery indexed/scan truth.
- [ ] Cover unchanged BM25 scores and ordering for default-adapted analyzers.
- [ ] Cover a V3-native positioned override consistently across index, scan, and BM25.
- [ ] Cover startup, bulk, dynamic build/replay, failure atomicity, and retry behavior.
- [ ] Add deterministic randomized differential coverage for membership, positions, TF,
  document length, total length, mutations, gaps, alternatives, and reorderings.

## Performance evidence

- [ ] Add or extend a focused positional text-index JMH/equivalent baseline.
- [ ] Record representative build/mutation throughput and allocation or retained-memory
  evidence.
- [ ] Confirm primitive occurrence storage and absence of an obvious boxing/pathological
  regression.
- [ ] Document results without claiming a universal speedup or implementing compression.

## Compatibility and scope audit

- [ ] Frozen v1 source/reflection fixture passes.
- [ ] Japicmp passes against 1.0.0, 2.0.0, and 2.1.0 in normal and isolated repositories.
- [ ] v1-, v2-, and v3-style independent consumers pass.
- [ ] Public API inspection confirms no public positions type or unintended descriptor.
- [ ] `PostingList` public descriptors and observable term-frequency behavior remain
  compatible.
- [ ] No phrase/fuzzy/bool/boost/cross-field/new-request/Explain execution is added.
- [ ] No planner/executor, compression, trie, automaton, offset, or unrelated refactor is
  added.
- [ ] `RankedSearcher`, `CandidatePlanner`, bitmaps, writer concurrency, and snapshot
  publication architecture are not redesigned.

## Documentation and full validation

- [ ] Update `CHANGELOG.md` after implementation.
- [ ] Record performance observations in the Phase 2 completion documentation.
- [ ] Mark Phase 2 complete in the roadmap and V3 phase map only after every gate passes.
- [ ] `git diff --check` passes.
- [ ] `scripts/verify-version-alignment.sh 3.0.0-SNAPSHOT` passes.
- [ ] `./mvnw -f reactor/pom.xml clean test` passes.
- [ ] `scripts/run-travel-example.sh` passes with unchanged observable output.
- [ ] `./mvnw clean -Papi-compat test` passes.
- [ ] `./mvnw clean -Partifact-compat verify` passes in normal and isolated repositories.
- [ ] `scripts/verify-consumer-projects.sh` passes.
- [ ] Strict core and processor Javadocs pass.
- [ ] `./mvnw -f reactor/pom.xml clean -Prelease -Dgpg.skip=true verify` passes.
- [ ] `scripts/verify-release-artifacts.sh 3.0.0-SNAPSHOT` passes.
- [ ] `scripts/verify-reproducible-build.sh` passes.
- [ ] No generated artifact, local repository, credential, IDE file, or local Codex
  prompt is tracked.

Phase 2 is complete only when the index retains correct positions, all current text
paths agree on positioned terms, and published legacy behavior remains unchanged for
default-adapted analyzers. Visible phrase or fuzzy execution is scope failure, not extra
progress.
