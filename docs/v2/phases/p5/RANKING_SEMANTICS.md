# GeneralSearchEngine v2 BM25 ranking semantics

## Status and scope

This document freezes the ranked-retrieval contract introduced and accepted in roadmap
phase P5. The implementation, correctness, compatibility, release, reproducibility,
and complete 70-row performance gates pass.

P5 adds relevance-ranked retrieval over one canonical analyzed text field. It does not
change existing `search(Query<T>)` truth, candidate safety, or ascending internal
document-ID result order.

## Public request boundary

Ranking is additive and separate from boolean `Query<T>`:

- `TextScoringQuery<T>` identifies one canonical `TextField<T>` and analyzed scoring
  terms;
- `RankedSearchRequest<T>` contains the scoring query, optional existing boolean
  filter, positive top-K limit, and immutable `Bm25Config`;
- `SearchHit<T>` contains the retained document reference and finite non-negative
  score;
- `SearchEngine.searchTopK(request)` returns ranked hits synchronously from one
  immutable snapshot.

`searchTopK` is a default interface method so v1 third-party `SearchEngine`
implementations do not gain a new abstract method. The built-in snapshot engine
overrides the capability. An implementation that does not support ranking throws
`UnsupportedOperationException`.

Ranked retrieval requires the installed `TextIndexSnapshot` to use the exact canonical
`TextField` instance from the scoring query. A non-empty scoring query without that
index fails with `IllegalStateException`; P5 does not fabricate scores through a full
document scan.

## Exact BM25 formula

For each distinct analyzed query term `t` present in document `d`:

```text
idf(t) = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

score(t, d) = idf(t) *
              (tf(t, d) * (k1 + 1)) /
              (tf(t, d) + k1 * (1 - b + b * dl(d) / avgdl))

score(d) = sum(score(t, d)) for every distinct scoring term
```

Where:

- `N` is the number of indexed documents whose analyzed field has at least one token;
- `df(t)` is exact posting document frequency;
- `tf(t,d)` is exact per-document term frequency;
- `dl(d)` is the analyzed token count including repeated tokens;
- `avgdl` is total analyzed token count divided by `N`.

The default configuration is `k1=1.2`, `b=0.75`. `k1` must be finite and non-negative;
`b` must be finite and within `[0,1]`. NaN and infinities are rejected.

## Query and field semantics

The scoring query uses the canonical field Analyzer defined by P4. Query terms are
deduplicated in first-encounter order, so repeated query text does not multiply term
weight. Repetition in a document does affect `tf`.

Candidates contain documents matching any distinct scoring term. A query that analyzes
to zero tokens returns an empty result. Null query text is rejected. Documents with
null, empty, or zero-token fields have `dl=0`, are excluded from `N`/`avgdl`, and cannot
be scoring candidates.

One request scores one `TextField`. Existing structured or text `Query<T>` instances
may be used as the eligibility filter, including boolean composition. Cross-field score
combination, boosts, query-term weights, and disjunction-max behavior are not defined in
P5.

## Filtering and top-K

Execution proceeds from immutable postings:

1. union scoring-term posting membership;
2. intersect an available optional-filter candidate bitmap;
3. evaluate the filter's final `Query.matches(document)` truth for every remaining
   scoring candidate;
4. calculate BM25 only for eligible documents;
5. retain at most K hits in a bounded min-heap;
6. sort retained hits by descending score and then ascending internal document ID.

Filter candidate accuracy may be `EXACT` or `SUPERSET`; final predicate verification
keeps eligibility correct. A filter with no index is evaluated only against scoring
candidates, not the complete snapshot.

The limit must be positive. `K=1`, `K=match count`, and `K>match count` are supported.
Equal scores use ascending internal document ID as a deterministic tie-break. Internal
IDs are deliberately not added to `SearchHit`; they remain an engine implementation
detail.

## Immutable metadata lifecycle

The text index snapshot atomically owns postings, term frequency, document frequency,
per-document analyzed length, total analyzed length, indexed-document count, and
average length. Add, update, remove, startup build, dynamic build, mutation replay, and
drop publish these facts through the existing immutable lifecycle.

Document lengths use a persistent path-copied integer dictionary. An old snapshot keeps
its old posting and length statistics after later mutations. Dynamic build completion
publishes replayed postings and length metadata together, so readers cannot combine
scores from different versions.

## Compatibility and exclusions

P5 adds new types and one default interface method. It does not change v1 public record
descriptors, the `IndexSnapshot<T>` SPI, unranked query truth, or unranked result order.

The following remain outside P5:

- phrase/position/offset queries and highlighting;
- fuzzy search, spelling correction, stemming, or query expansion;
- cross-field scoring, boosts, explanations, pagination/search-after, and distributed
  score merging;
- persistence/WAL and distributed search/sharding.

Performance evidence is environment- and workload-specific. See
[`PERFORMANCE_BASELINE.md`](PERFORMANCE_BASELINE.md).
