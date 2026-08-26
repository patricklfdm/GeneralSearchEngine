# V3 Phase 2 positional storage contract

## Status

The Phase 2 contract remains frozen and implementation is complete. The existing text
index is now position-capable without implementing phrase search or changing the
published behavior of legacy analyzers. Focused, randomized, lifecycle, performance,
compatibility, consumer, packaging, and reproducibility gates pass.

The Phase 0 positional semantics and Phase 1 position-aware analysis contract remain
authoritative. This document freezes the first consumer, storage, compatibility, and
failure boundaries that those earlier contracts intentionally deferred.

## Delivery boundary

Phase 2 introduces:

- an internal immutable primitive-backed `IntPositions` value;
- per-document positions in each `PostingList`;
- one-pass positioned document analysis in `TextIndexBuilder`;
- position-sensitive mutation and no-op detection;
- consistent positioned-term projection across current indexed, scan, and BM25 paths;
- focused, randomized, lifecycle, compatibility, and lightweight performance evidence.

Phase 2 does not expose positions publicly or execute phrase, fuzzy, bool, boost,
cross-field, new request, planner, executor, or Explain behavior.

## Positioned-analysis activation

Phase 2 is the first production consumer of
`Analyzer.analyzeWithPositions(String)`. The following internal paths must derive terms
from positioned output:

```text
TextIndexBuilder document analysis
TextQuerySupport query-term analysis
TextQuerySupport scan document analysis
TextScoringQuery term analysis
```

Term-only paths ignore increments after validating the complete positioned sequence.
They retain encounter order and their existing distinct-term rules. The index builder
uses both terms and increments.

This consistent activation is required to keep an exact text index equivalent to its
scan predicate. Migrating only index construction would permit a V3-native Analyzer
override to produce false-positive or false-negative `CandidateAccuracy.EXACT`
candidates.

All Analyzer implementations compiled before Phase 1 inherit the default adapter, so
their analyzed terms, query truth, term frequency, document length, BM25 scores, and
ordering remain exactly unchanged. A V3-native override intentionally begins affecting
all current text-analysis consumers in Phase 2; it must not affect only the index.

The existing public `TextField.analyzeDocument(T)` method retains its descriptor and
legacy `Analyzer.analyze(String)` behavior. Phase 2 adds no new public `TextField`
method.

## Positioned-output validation

Every Phase 2 consumer validates the entire Analyzer result before using it:

```text
returned list is non-null
each element is non-null
first token increment >= 1
later token increment >= 0
logical position never exceeds Integer.MAX_VALUE
```

`AnalyzedToken` already validates non-null/non-empty terms and non-negative increments.
Consumers must still defend against a null list, null element, invalid first increment,
and accumulated overflow. Logical position starts at `-1`; addition must not wrap.

Malformed output fails with `IllegalArgumentException` containing useful field and token
context. Analyzer-thrown exceptions propagate unchanged. Analysis and validation finish
before any builder state is mutated, preserving mutation and publication atomicity.

Consumers neither retain nor mutate an Analyzer-owned list.

## Logical positions and document length

For each emitted token:

```text
logicalPosition = logicalPosition + positionIncrement
record term at logicalPosition
tokenCount = tokenCount + 1
```

Initial gaps and later gaps are retained. Different terms may share a logical position.
For one term:

- occurrences at different positions are all retained;
- duplicate occurrences at the same position are represented once;
- stored positions are therefore strictly increasing.

Term frequency is the number of stored unique logical positions. Document length is the
number of emitted tokens, including a duplicate `(term, position)` that is represented
once in positions. It is never maximum logical position plus one.

Consequently, analyzed-document state is the value pair:

```text
Map<String, IntPositions> positionsByTerm
int tokenCount
```

Both components participate in equality and no-op detection.

## `IntPositions`

`IntPositions` is a package-private final value type in the text-index implementation
package. It is backed by privately owned primitive storage and provides, conceptually:

```java
int size()
int get(int index)
boolean contains(int position)
```

Its values are non-negative and strictly increasing. Construction defensively copies
caller-owned arrays or builders. No method exposes a mutable backing array. Equality and
hash code are value-based and deterministic. Empty values are valid.

Phase 2 does not add compression, delta encoding, varints, packed blocks, off-heap
storage, or boxed `List<Integer>` occurrence storage.

## `PostingList` storage and public compatibility

The internal representation becomes:

```text
PostingList
├── ImmutableBitmap documents
└── PersistentAvlMap<Integer, IntPositions> positionsByDocument
```

`termFrequency(docId)` returns the stored positions size or zero when absent. Bitmap
membership, position-map membership, and positive term frequency remain equivalent.

Every existing public method and JVM descriptor remains available:

```java
PostingList.empty()
documents()
documentFrequency()
termFrequency(int)
withTermFrequency(int, int)
without(int)
```

`withTermFrequency` retains its current argument validation and observable membership,
frequency, and same-frequency no-op semantics. When it must create a new value, it uses
synthetic sequential positions `0..frequency-1`; this preserves the legacy frequency
contract without retaining a duplicate frequency map. Normal text-index construction
uses an internal position-aware update path instead.

The position-aware update and read operations are package-private. An absent document
reads as empty positions. No public positions method, raw array, or supported positional
SPI is added.

## Builder mutation and no-op semantics

`TextIndexBuilder` analyzes each supplied old or new document exactly once per index
operation. One positioned pass derives membership, frequency, positions, and token
count. It does not run separate legacy, BM25, and phrase analysis passes.

An update is a no-op only when both `positionsByTerm` and `tokenCount` are value-equal.
Equal frequency maps are insufficient: reordering `"java search"` to
`"search java"` changes positions and must update postings.

Changed terms are determined by comparing `IntPositions` values. A term whose position
list changes must be republished even when its size is unchanged. Document-length state
must also publish when token count changes but deduplicated positional maps do not.
Therefore `dirty.isEmpty()` alone is not a sufficient whole-builder no-op test.

All validation and exact arithmetic complete before the corresponding persistent state
references are assigned. Failed add, update, remove, bulk mutation, startup build, or
dynamic build/replay publishes neither partial postings nor partial ranking metadata.

Removing a document clears bitmap membership and positions. A posting with no documents
is removed from the term dictionary according to existing behavior.

## Snapshot and query compatibility

The following behavior remains unchanged for legacy/default-adapted analyzers:

```text
posting(term)
documentLength(docId)
totalDocumentLength()
averageDocumentLength()
documentsContainingAny(...)
TermQuery / AnyTermsQuery / AllTermsQuery truth
candidate accuracy and estimates
IndexStatistics
BM25 inputs, scores, and deterministic order
```

Old snapshots retain their owned position arrays and persistent maps after later
mutations. New snapshots publish atomically and structurally share unchanged posting and
document-length state. No mutable array crosses a snapshot boundary.

Startup indexes, add/update/remove, bulk operations, dynamic `createIndex`, mutation
replay during a background build, drop/recreate, analyzer failure, and retry behavior
all remain supported.

## Verification boundary

Focused tests cover `IntPositions`, positioned-output validation, repeated terms, gaps,
same-position alternatives, duplicate `(term, position)` handling, initial gaps,
position overflow, term-frequency compatibility, order-sensitive updates, length-only
updates, remove cleanup, no-op reuse, and snapshot isolation.

Randomized differential tests compare production state with a simple reference model
for membership, positions, term frequency, document length, and total document length
across adds, updates, reorderings, removals, gaps, and same-position alternatives.

Engine lifecycle tests cover startup and dynamic build/replay. Existing boolean and
ranked differential suites protect query truth and BM25. Position assertions use
same-package tests or test-only bridges; production visibility is not widened for tests.

A focused Phase 2 JMH or equivalent repeatable baseline records positional text-index
build/mutation throughput and allocation or retained-memory evidence at representative
sizes. It is a regression record, not a compression or optimization project.

Japicmp must pass against 1.0.0, 2.0.0, and 2.1.0, including an isolated Maven
repository. The v1-, v2-, and v3-style consumers, strict Javadocs, release artifacts,
travel example, and reproducible-build gates remain required.

## Explicit non-goals

Phase 2 must not implement or expose:

- public positions or mutable-array access;
- phrase planning, matching, scoring, or slop;
- `SearchPlanner`, `SearchPlan`, or `SearchExecutor`;
- built-in `SearchEngine.search(SearchRequest)` execution;
- legacy ranked-request routing through new internals;
- bool, boost, or cross-field ranked execution;
- fuzzy expansion or edit distance;
- Explain execution;
- position compression, offsets, highlighting, tries, or automata;
- changes to `RankedSearcher`, `CandidatePlanner`, bitmap representations, writer
  concurrency, or snapshot publication architecture;
- unrelated cleanup or refactoring.
