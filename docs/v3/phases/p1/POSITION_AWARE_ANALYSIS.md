# V3 Phase 1 position-aware analysis contract

## Status

The Phase 1 contract remains frozen and its implementation is complete. Phase 1 adds
the position-aware Analyzer model required by later positional indexing without
changing any existing text-query, indexing, BM25, or engine behavior.

The Phase 0 positional contract remains authoritative. This document makes its Phase 1
delivery boundary and verification requirements executable.

## Goal and boundary

Phase 1 adds exactly two public API elements in
`io.github.patricklfdm.generalsearch.analysis`:

```java
public record AnalyzedToken(String term, int positionIncrement) {
}
```

```java
default List<AnalyzedToken> Analyzer.analyzeWithPositions(String text)
```

It does not add a positional consumer. Existing production paths continue calling
`Analyzer.analyze(String)` and using `Token`. Consequently, a custom override of
`analyzeWithPositions` has no effect on V2 boolean text search, text indexes, BM25, or
the Phase 0 V3 request façade during Phase 1.

## `AnalyzedToken` contract

`AnalyzedToken` is a public immutable record with record components in this order:

```text
term
positionIncrement
```

Construction rules are part of the public contract:

```text
null term:
IllegalArgumentException

empty term:
IllegalArgumentException

negative positionIncrement:
IllegalArgumentException
```

Whitespace is not independently rejected. Normalization and linguistic meaning remain
the Analyzer's responsibility, just as with the existing `Token`. Increment zero is
valid at the record boundary because it represents a same-position alternative after
another token.

The record defines no offsets, token type, payload, keyword flag, source length, or
absolute position.

## Default Analyzer adapter

Adding `analyzeWithPositions` as a default method must preserve `Analyzer` as a
functional interface. Its implementation is frozen as the ordered projection of one
legacy analysis call:

```java
default List<AnalyzedToken> analyzeWithPositions(String text) {
    return analyze(text).stream()
            .map(token -> new AnalyzedToken(token.term(), 1))
            .toList();
}
```

Required observable behavior:

- invoke `analyze(text)` exactly once with the original reference, including null;
- propagate an exception from `analyze` unchanged;
- preserve encounter order and duplicate tokens;
- preserve every term string exactly;
- assign `positionIncrement = 1` to every emitted token;
- return an unmodifiable list;
- return an empty list when legacy analysis returns an empty list;
- perform no caching, normalization, deduplication, filtering, or position inference.

Direct behavior for an invalid legacy Analyzer that returns a null list or null token is
not a new compatibility promise. Existing Analyzer output is already required to be
valid. The first future planner/index consumer must validate all positioned output and
report malformed output as `IllegalArgumentException` with useful context.

## Custom position-aware Analyzer contract

An Analyzer may override `analyzeWithPositions`. Its output is consumed in deterministic
encounter order and must satisfy:

```text
returned list is non-null
each element is non-null
each term is non-empty
first token increment >= 1
later token increment >= 0
```

Logical positions are computed from `-1` by adding each increment. Zero is valid only
after the first token and represents a same-position alternative. A future consumer
must reject a sequence whose logical position would exceed `Integer.MAX_VALUE`; it must
not wrap. Empty output is valid.

The record constructor enforces token-local rules. The first-token rule and accumulated
position overflow are sequence-level rules and are intentionally enforced by the first
planner/index consumer, not by Phase 1 API construction.

Custom analyzers remain responsible for determinism, thread safety, and independence
from locale, time zone, mutable external state, and invocation history. Consumers must
not retain or mutate an Analyzer-owned output list.

## Compatibility boundary

Phase 1 must preserve all of the following:

- `Analyzer` retains exactly one abstract method and remains usable as a lambda;
- existing compiled Analyzer implementations inherit the default method;
- `Token` retains its existing record descriptor and validation behavior;
- `Analyzer.simple().analyze(text)` returns exactly the existing terms and order;
- `Analyzer.simple().analyzeWithPositions(text)` uses the default all-ones adapter;
- `TextField`, `TextQuerySupport`, `TextScoringQuery`, and `TextIndexBuilder` are not
  migrated to positioned analysis in Phase 1;
- existing query truth, term frequency, document length, BM25 scores, result ordering,
  index lifecycle, and snapshot publication remain unchanged.

Japicmp must continue passing against published 1.0.0, 2.0.0, and 2.1.0. The v1-, v2-,
and v3-style consumers must continue compiling. The v3 consumer should additionally
compile representative `AnalyzedToken` construction and legacy-lambda adaptation.

## Implementation slices

### Slice 1 — public model and default method

- add `AnalyzedToken.java` with strict Javadocs and frozen validation;
- add the default method and strict Javadocs to `Analyzer`;
- do not override the method in `SimpleAnalyzer` unless a test proves the default cannot
  express the frozen behavior.

### Slice 2 — focused contract tests

- add `AnalyzedTokenTest` for record shape, accessors, valid zero/positive increments,
  and all constructor failures;
- extend `SimpleAnalyzerTest` for all-ones positional projection and unchanged terms;
- add `AnalyzerPositionCompatibilityTest` for lambda/SAM compatibility, one-call
  delegation, original-input identity, duplicates, immutable output, empty output,
  exception propagation, and a custom positional override;
- use reflection only to protect the public record-component order and single abstract
  method count, not internal implementation details.

### Slice 3 — compatibility and documentation

- extend the v3 independent consumer with position-aware API compilation;
- update `CHANGELOG.md` and the V3 phase map after implementation;
- run all correctness, compatibility, consumer, Javadoc, artifact, and reproducibility
  gates before marking Phase 1 complete.

## Explicit non-goals

Phase 1 must not:

- change existing Analyzer term production;
- migrate `TextField` or any query/index/ranking call site to `analyzeWithPositions`;
- add a public validation utility or another Analyzer abstract method;
- add `IntPositions`, positional postings, absolute positions, or offsets;
- change `PostingList`, `TextIndexBuilder`, `TextIndexSnapshot`, or BM25 metadata;
- implement phrase planning/matching/scoring, fuzzy execution, or same-position synonym
  query semantics;
- implement `SearchPlanner`, `SearchPlan`, `SearchExecutor`, or Explain execution;
- add stemming, stop words, synonym dictionaries, highlighting, or unrelated cleanup.

No benchmark is required because Phase 1 does not put the new method on a production
execution path. Performance evidence begins when a later phase consumes positioned
analysis during index construction or request planning.
