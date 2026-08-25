# GeneralSearchEngine v2 analyzed-text semantics

## Status and scope

This document freezes the unranked analyzed-text contract introduced in roadmap phase
P4. It is additive to the published v1 API and applies to the current
`2.0.0` release.

P4 provides deterministic tokenization, term membership queries, and an immutable
inverted index. It does not provide scoring, ranked top-K retrieval, phrase or position
queries, fuzzy expansion, stemming, persistence, or distributed search. BM25 and
ranking remain P5 work.

## Canonical text fields

A `TextField<T>` pairs one `Field<T, String>` with one `Analyzer`. The pairing is
schema-owned and identity-based:

- one logical schema field name has at most one canonical `TextField`;
- startup and dynamically created text indexes must reference that exact canonical
  `TextField` instance;
- a manually assembled engine registers the canonical text field when
  `IndexDefinition.text(textField)` is added;
- a fixed schema rejects a competing `TextField`, even if its field and Analyzer happen
  to behave equivalently;
- different analysis configurations over the same source property require distinct
  logical field names and therefore distinct `Field`/`TextField` instances.

These rules prevent an index and its scan fallback from assigning different meanings
to the same query.

Custom analyzers must be deterministic, thread-safe, locale/time-zone independent, and
safe for concurrent reads and background index builds. Analyzer output is consumed in
encounter order and may contain repeated tokens, but must not contain null tokens.

## Simple Analyzer

`Analyzer.simple()` applies these rules in order:

1. null and empty input produce zero tokens;
2. normalize the input with Unicode NFKC;
3. convert case with `String.toLowerCase(Locale.ROOT)`;
4. retain consecutive Unicode letters and digits in one token;
5. treat every other code point, including whitespace and punctuation, as a boundary;
6. preserve token encounter order and repetitions.

Token equality is exact Java `String` equality after those transformations. No
stop-word removal, stemming, accent removal, locale-specific segmentation, offsets, or
positions are applied. For example, full-width Latin text is compatibility-normalized,
while Chinese text separated by punctuation forms separate tokens.

## Query truth

All text queries analyze query text and document text with the same canonical Analyzer.
`Query.matches(document)` remains the final truth oracle whether an index is present or
the engine scans the snapshot.

| Query | Frozen behavior |
|---|---|
| `Query.term(field, text)` | Query text must analyze to exactly one distinct term; otherwise construction fails with `IllegalArgumentException`. Repeating that same term is allowed. |
| `Query.anyTerms(field, text)` | Matches when the document contains at least one distinct analyzed query term. |
| `Query.allTerms(field, text)` | Matches when the document contains every distinct analyzed query term. |

For all query forms, null query text is rejected. `anyTerms` and `allTerms` deduplicate
query terms in first-encounter order. If their query input produces zero tokens, they
match no documents; zero-token `allTerms` is deliberately not an implicit MatchAll.

A null, empty, or punctuation-only document field contains no terms. Repeated document
terms do not change boolean membership, although their frequency is retained in the
posting list for the separately scoped P5 ranking phase.

Text queries compose with existing AND, OR, NOT, MatchAll, equality, range, and prefix
queries under their established semantics. Unranked result order remains ascending
internal document-ID order.

## Index and lifecycle behavior

`IndexDefinition.text(textField)` creates an immutable term dictionary backed by the
P2 persistent AVL representation. Each term maps to an immutable `PostingList` with:

- an exact document-membership bitmap;
- exact document frequency;
- immutable per-document term frequency.

Positions and offsets are intentionally absent. Term-frequency storage is readiness
for P5, not a P4 scoring feature.

Term, any-terms, and all-terms candidates are `EXACT`. Any-terms unions postings with a
single mutable bitmap accumulator and one freeze. All-terms starts with the smallest
posting and intersects immutable bitmaps. Multi-term cardinality estimates may be
`APPROXIMATE`, but candidate accuracy remains `EXACT`; estimate error can affect cost,
never correctness.

Text indexes participate in the existing immutable publication lifecycle: startup
build, add, update, remove, background dynamic build, mutation replay, atomic install,
drop, failure recovery, and close. A document that analyzes to zero tokens is retained
in the snapshot but is not included in the text index's indexed-document statistic.
Unchanged builders reuse their base snapshot; changed term dictionary nodes are
path-copied rather than copying the complete vocabulary.

## Compatibility and exclusions

P4 adds public types and static factories without changing v1 public record descriptors
or the `IndexSnapshot<T>` extension SPI. If no compatible text index is installed,
search remains correct through exhaustive analysis and final predicate evaluation.

The following remain outside P4:

- BM25, relevance scores, ranked top-K, or a new text-specific/direct-query cost
  crossover policy (the existing P3 composite planner may consume generic estimates);
- phrase queries, token positions, offsets, highlighting, fuzzy matching, spelling
  correction, or automatic linguistic expansion;
- persistence/WAL and distributed search/sharding.

Performance measurements are regression baselines for their recorded environment and
workload, not universal guarantees. See
[`PERFORMANCE_BASELINE.md`](PERFORMANCE_BASELINE.md).
