# V3.1 ranked-search semantics

This contract is additive to the frozen
[V3.0 ranked-search semantics](../../v3/phases/p0/SEARCH_SEMANTICS.md),
[positional semantics](../../v3/phases/p0/POSITIONAL_SEMANTICS.md), and
[fuzzy semantics](../../v3/phases/p0/FUZZY_SEMANTICS.md). Rules not explicitly changed
here remain unchanged.

## Phrase slop public model

V3.1 adds:

```java
SearchQueries.phrase(TextField<T> field, String text, int slop)
```

`slop` is an integer greater than or equal to zero. A negative value fails immediately
with `IllegalArgumentException`. Null field and text validation remains identical to
the existing factory. The existing `phrase(field, text)` factory is exactly equivalent
to `phrase(field, text, 0)` in representation-independent observable behavior.

Slop is retained in the immutable façade and is not analyzer configuration. Boosting
the returned query changes score only and does not change slop.

## Ordered gap-budget definition

Positioned query analysis uses the V3.0 validation and slot normalization rules. Let
the normalized query slots have strictly increasing relative positions:

```text
r[0] = 0 < r[1] < ... < r[n-1]
```

Each slot retains its ordered, deduplicated same-position alternatives. A document
witness selects one indexed occurrence position `p[i]` matching an alternative in
each slot. It is valid when:

```text
p[i] - p[i-1] >= r[i] - r[i-1]        for every i > 0

consumedSlop = (p[n-1] - p[0]) - (r[n-1] - r[0])

consumedSlop <= requestedSlop
```

All subtractions and comparisons use overflow-safe arithmetic. This is an ordered
extra-gap budget:

- term order cannot change;
- query position gaps are minimum required gaps and cannot contract;
- transposition is not supported;
- one-slot phrases consume zero slop;
- repeated terms in different slots require distinct ordered positions;
- same-position alternatives remain one slot and do not consume slop;
- an initial analyzer gap is validated and normalized away exactly as in V3.0.

This definition is intentionally not described as Lucene phrase slop.

## Phrase candidates, match, and score

Candidate generation remains the intersection across slots of the union of each
slot's alternative postings. It is exact with respect to term presence and a safe
superset with respect to positional truth. Physical ordering or anchor selection may
change but cannot remove a valid witness.

Slop affects match truth only. Once matched, phrase score remains the sum of ordinary
field-local BM25 contributions for distinct analyzed phrase terms in analyzer
first-encounter order. V3.1 adds no phrase-frequency bonus, proximity bonus, slop
penalty, coordination factor, or hidden boost.

Zero analyzed slots match nothing and return before canonical text-index resolution.
Missing-index and whole-tree validation precedence remains the V3.0 precedence.

## Phrase Explain

Normal search and Explain use the same normalization, candidate, positional truth, and
BM25 arithmetic. Explain reports the requested slop and, for a match, the minimum
consumed slop among valid witnesses. It does not expose raw positions, posting handles,
the selected anchor, candidate bitmaps, or internal document IDs. Description strings
remain diagnostic and are not a parseable serialization format.

## `minimumShouldMatch` public model

V3.1 adds one optional setting to `SearchQueries.BoolBuilder<T>`:

```java
BoolBuilder<T> minimumShouldMatch(int value)
```

The mutable builder retains the last supplied value and immutable `build()` snapshots
do not observe later builder changes. A negative value fails immediately. Final
shape-dependent validation occurs at `build()`:

- a value greater than the declared SHOULD occurrence count is invalid;
- explicit zero is valid only when at least one MUST occurrence exists;
- an empty BOOL remains invalid.

When the setting is absent, V3.0 behavior is preserved exactly:

```text
MUST present    -> effective minimumShouldMatch = 0
MUST absent     -> effective minimumShouldMatch = 1
```

## BOOL match and score

A BOOL matches when every MUST occurrence matches and at least the effective number of
SHOULD occurrences matches. Each builder occurrence counts independently; duplicate
clauses are neither deduplicated nor collapsed, including a query added more than once
or present in both MUST and SHOULD.

A zero-term leaf never matches and therefore never contributes to the matched SHOULD
count. Validation against the SHOULD count uses declared occurrences, not the number
of non-empty normalized children. Each nested BOOL computes its own effective minimum.

The score remains the checked deterministic sum of all MUST scores followed by all
matching SHOULD scores in builder encounter order. Evaluation cannot stop scoring
after the minimum is met. Matched zero-score children count as matched. Boost wraps the
completed child score and never changes the child's matched-clause count.

Candidate planning may construct an exact threshold bitmap or a conservative superset.
It must intersect mandatory candidates, cannot drop a document that could meet the
threshold, and must leave final logical counting to the scoring plan. Structured
`SearchRequest.filter` remains a separate zero-score eligibility layer.

Explain reports the effective minimum, matched SHOULD count, and ordered child
diagnostics. Its final matched state and score equal normal search exactly.

## V3.1 fuzzy behavior

The supported V3.1 fuzzy factory and semantics are unchanged. AUTO continues to use
maximum edit distances `0`, `1`, or `2`; expansion remains complete; distance remains
Unicode-code-point Optimal String Alignment; exact-term priority, similarity,
max-not-sum scoring, expansion ordering, and Explain tie-breaking remain unchanged.

V3.1 changes only physical dictionary representation and traversal. It adds no public
maximum-edit, prefix-length, or maximum-expansion control. A future explicit expansion
cap is a new recall contract and cannot alter the existing factory default.

## Explicit exclusions

V3.1 adds no ranked `mustNot`, pure-negative ranked BOOL, phrase transposition, phrase
slop scoring adjustment, fuzzy phrase, multi-token fuzzy, hidden expansion truncation,
BM25F, DisMax, custom scoring, pagination, total hits, offsets, highlighting, synonyms,
stemming, persistence, vector retrieval, or distributed retrieval.
