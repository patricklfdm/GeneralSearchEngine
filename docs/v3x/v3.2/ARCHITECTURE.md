# V3.2 architecture contract

## Boundary

V3.2 adds offset-capable analysis and snapshot-consistent structured highlighting to
the existing V3 ranked pipeline. It does not add another planner, another query model,
or a second search invocation per hit:

```text
HighlightedSearchRequest
  -> request / field / capability validation
  -> one captured immutable SearchSnapshot
  -> existing whole-tree normalization and snapshot-bound SearchPlan
  -> existing candidate, scoring, and bounded top-K execution
  -> offset re-analysis of only the returned documents
  -> leaf witness reconstruction from the same normalized plan
  -> deterministic field / fragment / span assembly
  -> HighlightedSearchResult
```

The embedded `SearchRequest` has exactly the same match, score, order, limit, filter,
and failure semantics as an ordinary V3.1 search. Highlighting is derived output. It
cannot change candidate construction, score arithmetic, top-K membership, tie-breaking,
or Explain.

## Additive analyzer capability

The published `Analyzer` interface remains a SAM and the published `AnalyzedToken`
record retains exactly `term` and `positionIncrement`. V3.2 introduces a separate
`OffsetAnalyzer` capability and an immutable `OffsetAnalyzedToken` value. An analyzer
configured on a `TextField` supports highlighting only when the configured object also
implements that capability.

`OffsetAnalyzer` supplies default legacy `analyze` and `analyzeWithPositions` adapters
from its offset-aware output so a new custom implementation can have one source of
truth. The built-in `SimpleAnalyzer` must override the ordinary analysis methods and
retain the existing non-offset path. Indexing, ordinary search, and Explain therefore
do not allocate offset tokens merely because the built-in analyzer supports the new
capability.

The offset-aware and ordinary outputs for the same non-null text must contain identical
term and logical-position sequences. Offsets add source mapping only; they cannot alter
normalization, stop-word gaps, same-position alternatives, indexed terms, document
length, scoring terms, or phrase positions.

## Re-analysis instead of stored offsets

V3.2 does not store character offsets in `TextIndexSnapshot`, postings, position lists,
the fuzzy trie, or another per-document sidecar. The engine already retains immutable
document references, and highlighted search is bounded by the existing top-K limit.
The implementation re-extracts and re-analyzes only requested fields of returned hits.

This choice is frozen for V3.2 because it:

- leaves the 1M-document retained index shape unchanged;
- adds no offset payload to every token of every active snapshot;
- avoids offset copy/update work during ordinary mutation and dynamic-index replay;
- charges offset allocation only to an explicit highlighted-search request;
- uses the same deterministic, thread-safe analyzer configured for indexing; and
- can be replaced by stored offsets only in a later contract backed by retained-memory
  and latency evidence.

Document immutability remains mandatory. A consumer that mutates an accepted document
or its text value already violates the engine contract and receives no highlighting
consistency guarantee.

## One-snapshot result assembly

`search(HighlightedSearchRequest<T>)` is one engine operation. The implementation
captures one snapshot, obtains hits, resolves the retained document references, and
builds highlights before releasing that invocation's snapshot context. It must not be
implemented as a public ordinary `search` followed by public `get` or `explain` calls,
because a mutation could publish between those calls.

Every `HighlightedSearchHit` wraps the exact `SearchHit` produced by the canonical
executor. Highlight order follows hit order. Requested field order follows request
order. No result object exposes the snapshot, internal document ID, plan, posting,
position list, trie, candidate bitmap, or mutable analyzer output.

## Internal match evidence

The highlighter may add package-private evidence carriers or visitors to the scoring
plan. They are invocation-local and may contain only the normalized leaf identity and
the bounded facts required to reconstruct visible spans for returned documents.

The evidence boundary is:

- TEXT: normalized terms whose occurrences matched that leaf;
- PHRASE: the deterministic selected positional witness;
- FUZZY: the expansion selected by existing per-document fuzzy score/tie rules;
- BOOL: every matched MUST and matching SHOULD child that participates in the final
  logical evaluation;
- BOOST: the child's evidence unchanged; and
- structured filters: no highlight evidence.

Evidence collection cannot be required for ordinary search or Explain. It is enabled
only by highlighted search and remains bounded by returned hit count, requested field
count, query size, analyzed token count, and configured fragment cap. No global mutable
cache or unbounded `ThreadLocal` storage is allowed.

## Fragment assembly

Offset re-analysis produces source ranges in the original field string. Leaf evidence
selects ranges, duplicate ranges are deduplicated, and overlapping ranges are merged.
Non-overlapping adjacent ranges remain separate unless a phrase witness explicitly
creates one covering range.

Fragment windows are then expanded by the requested UTF-16 context count, adjusted so
they do not split a surrogate pair, and coalesced when their windows overlap. Final
fragments are ordered by absolute start offset; the earliest configured number is
retained. Each fragment contains the exact source substring and absolute spans that it
contains. The library emits no HTML and performs no escaping or markup insertion.

## Publication and lifecycle

V3.2 changes no writer, publication, or dynamic-index state. Mutation and index builds
continue to publish terms, positions, document lengths, postings, and fuzzy vocabulary
atomically. Offset re-analysis reads the document and canonical `TextField` from the
same captured snapshot/schema view used by the highlighted search.

A close, invalid query, missing text index, noncanonical field, unsupported analyzer,
invalid offset output, extractor failure, or analyzer failure fails the complete
highlighted-search invocation. No partial result is returned. Concurrent ordinary
search, Explain, mutation, index build/drop, and close retain their V3.1 behavior.

## Implementation order and exclusions

Implementation proceeds in isolated steps:

1. compatibility fixtures and pre-change allocation/latency baselines;
2. offset token and analyzer capability with built-in SimpleAnalyzer equivalence;
3. highlighted request/result model and TEXT support;
4. PHRASE, FUZZY, BOOL, and BOOST evidence composition;
5. randomized, lifecycle, concurrency, compatibility, and performance hardening.

Analyzer pipelines, synonyms, stemming, and ranked prefix require independent contracts
after the offset/highlighting foundation. Multi-token synonyms require position length
or a token graph and are outside V3.2. V3.2 also adds no HTML renderer, completion
engine, search-after, total-hits mode, timeout, persistence, vector retrieval, or
distributed coordination.
