# V3 ranked-search semantics

These semantics are frozen in Phase 0 and implemented in later phases. Existing
structured and V2 ranked behavior is unchanged.

## Text

A text leaf matches when at least one distinct analyzed query term occurs. Its score is
the sum of BM25 contributions for matching distinct terms. Duplicate terms in one leaf
do not multiply query weight; scoring follows analyzer first-encounter order. Zero
analyzed terms match nothing.

## Phrase

A phrase matches the exact relative-position slot sequence defined in
[POSITIONAL_SEMANTICS.md](POSITIONAL_SEMANTICS.md); V3.0 slop is zero. Repeated tokens
remain significant for eligibility. After a match, each distinct analyzed phrase term
occurring in the document contributes BM25 once per phrase leaf, in query-analysis
first-encounter order. Zero analyzed tokens match nothing.

## Bool

When MUST clauses exist, every MUST must match. Score is the sum of all MUST scores plus
matching SHOULD scores. Without MUST clauses, at least one SHOULD must match and score
is the sum of matching SHOULD scores.

Clause order is builder encounter order. Duplicate clauses are retained and evaluated
once per occurrence, including a query present in both lists. There is no coordination
factor, implicit normalization, clause deduplication, `mustNot`, filter clause, or
`minimumShouldMatch` in V3.0.

## Boost

Boost changes score, never matching:

```text
match(boost(q, x)) = match(q)
score(boost(q, x)) = score(q) * x
```

Boosts are finite and strictly positive. Nested boosts multiply.

## Structured filter

`SearchRequest.filter(Query<T>)` affects eligibility only and always contributes zero
score. Index choice cannot change relevance semantics.

## Cross-field BM25

Each field computes BM25 from its own `N`, `df`, `dl`, and `avgdl`; clause scores from
different fields are added directly. V3.0 defines no BM25F, DisMax, field
normalization, or coordination bonus.

## Determinism and finite scores

Logical score accumulation uses analyzer term order, then MUST builder order, then
SHOULD builder order. Results sort by score descending and then internal document ID
ascending; internal IDs are not exposed.

Every intermediate and public score is finite and non-negative. Any multiplication or
addition producing NaN, infinity, or a negative value fails with `ArithmeticException`;
evaluation does not clamp, wrap, drop a contribution, or construct a non-finite hit.
Normal search and Explain share this behavior.
