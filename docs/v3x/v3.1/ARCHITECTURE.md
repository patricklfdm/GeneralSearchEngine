# V3.1 architecture contract

## Boundary

V3.1 extends the existing snapshot-bound ranked pipeline. It does not add a second
planner or execution path:

```text
SearchRequest
  -> whole-tree validation
  -> one positioned normalization per leaf occurrence
  -> snapshot-bound SearchPlan
  -> candidate iteration and deterministic scoring
  -> bounded top-K / Explain
```

Legacy `searchTopK(RankedSearchRequest)` continues to pass already-frozen V2 terms into
the canonical text path without re-analysis. Phrase slop and
`minimumShouldMatch` are V3 façade capabilities and do not alter that adapter.

## Public and normalized representation

The package-private phrase leaf retains a non-negative slop value. The existing
two-argument public phrase factory creates the same internal value as an explicit zero.
Positioned analysis, slot grouping, distinct phrase scoring terms, canonical-field
identity checks, and missing-index precedence remain centralized in
`RankedSearchInput` or its internal successor.

The package-private BOOL node retains an optional explicit minimum. Normalization
resolves it to an effective integer after whole-tree shape validation. Public façade
objects do not expose their node, normalized terms, slots, candidates, or plan.

## Sloppy phrase planning and verification

Planning prepares immutable primitive-oriented data:

- relative slot positions;
- posting alternatives per slot;
- slot-union candidate cardinalities;
- distinct scoring postings in analyzer encounter order;
- requested slop;
- a deterministic rarest-slot anchor, with lower slot index breaking ties.

Candidates remain the cardinality-ordered intersection of slot unions. Slop does not
widen term-presence candidates.

For each candidate document, verification iterates anchor occurrences in ascending
position order. For one anchor occurrence it chooses, slot by slot, the latest eligible
occurrence to the left and the earliest eligible occurrence to the right while
respecting each normalized minimum gap. Those choices minimize the witness span for
that anchor. A witness matches when its span inflation is within the requested slop.
The zero-slop path may retain a specialized exact-relative-position fast path.

Alternative-position merging and directional lookup operate on primitive stored
positions and must not allocate a collection per candidate document. Search may stop
at the first valid witness. Explain may continue to determine minimum consumed slop.
No global mutable or unbounded `ThreadLocal` scratch state is permitted; any scratch
storage is invocation-local and bounded by query slot count.

The existing Javadoc-hidden `PhrasePositionAccess` bridge may receive the narrow
additive operation needed for bounded-slop verification. It returns only internal
match/diagnostic scalars and never returns positions, arrays, iterators, postings,
snapshots, or internal document IDs to supported application code.

## BOOL planning and execution

MUST candidate composition remains an intersection. With an effective SHOULD minimum
of zero, SHOULD candidates do not affect eligibility. With a positive minimum,
planning may use a threshold bitmap when evidence supports it; otherwise the union of
SHOULD candidates is a safe superset. Final evaluation counts logical child matches
and scores all matching children in frozen encounter order.

Nested nodes retain independent match state. Candidate truth and scoring truth remain
separate so a matched zero-score child is never mistaken for a non-match.

## Persistent fuzzy dictionary

V3.1 selects an immutable persistent Unicode-code-point trie as the physical fuzzy
vocabulary index. It is stored alongside the posting dictionary in each
`TextIndexSnapshot` but remains package-private and unsupported.

Trie properties are frozen as follows:

- each edge is one Unicode code point, ordered by numeric code-point value;
- a terminal retains the canonical normalized term string but no `PostingList`;
- nodes and unchanged paths are structurally shared between snapshots;
- ordinary posting-frequency changes do not change trie membership;
- a path is added only when a term's posting changes from empty to non-empty;
- a path is removed only when a term's posting changes from non-empty to empty;
- postings and trie membership publish atomically in the same text-index snapshot.

The query traversal computes exact bounded OSA state over trie prefixes and visits
every terminal within the requested bound. Pruning is permitted only from a proven
lower bound and is covered by exhaustive and randomized comparison with the retained
full-vocabulary-scan oracle. Traversal output is sorted by the existing distance then
numeric-code-point order before candidate and scoring preparation. Exact-term priority
and posting lookup remain in the search layer.

The existing Javadoc-hidden `FuzzyVocabularyAccess` bridge may gain one narrow
distance-bounded visitation method using standard JDK callback types. The bridge may
visit `(term, distance)` facts but returns no trie, node, collection, posting, iterator,
snapshot handle, candidate, or plan and retains neither callback nor snapshot. The
existing complete vocabulary visitor remains available for compatibility validation
and differential tests. No supported vocabulary or fuzzy-index SPI is added.

## Publication and lifecycle

`TextIndexBuilder` updates trie membership only after the final dirty posting state for
the publication is known. Bulk mutation still creates one atomic snapshot publication.
Dynamic text-index construction builds postings, lengths, positions, and trie under
one captured base; journal replay updates all four consistently before installation.
Drop, cancellation, close, failed analysis, failed build, and rejected mutation cannot
publish a partial dictionary.

Every search and Explain call observes exactly one snapshot containing mutually
consistent postings and trie membership. A fuzzy plan never retains data from another
snapshot.

## Performance-change discipline

Phrase and fuzzy internal changes land independently after focused profiles. A broad
scoring-carrier rewrite, global plan cache, prepared query, bitmap format change, or
writer redesign is outside V3.1 unless separate evidence identifies it as necessary
and the contract is amended before implementation.
