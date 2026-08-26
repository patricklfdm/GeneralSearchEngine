# V3 fuzzy semantics

This is a frozen later-phase contract. Phase 0 retains raw fuzzy requests but performs
no analysis, expansion, edit-distance calculation, or execution.

## Analysis and distance

`SearchQueries.fuzzy(field, text)` represents one analyzed term. Planning maps zero
terms to match-nothing, accepts exactly one, and rejects multiple terms with
`IllegalArgumentException` before candidate evaluation. Search and Explain use the same
validation timing.

AUTO distance uses normalized query Unicode code-point length:

| Length | Maximum distance |
|---|---:|
| 0–2 | 0 |
| 3–5 | 1 |
| 6+ | 2 |

Distance is Optimal String Alignment over Unicode code points: insertion, deletion,
substitution, and adjacent transposition are supported, and no substring is edited more
than once. UTF-16 code units, locale, and collation do not define distance or ordering.

## Expansion and score

Expansion includes every indexed vocabulary term within the bounded distance;
candidates are the union of their postings. If the exact normalized term occurs in a
document, the leaf score is its exact BM25 and other expansions are ignored for that
document. Otherwise the leaf score is:

```text
max(BM25(expansion, document) * similarity(query, expansion))

similarity = 1 - distance / max(codePointLength(query), codePointLength(expansion))
```

Scores from expansions in one fuzzy leaf are never summed.

Expansion order is distance ascending, then lexicographic comparison of the numeric
sequence from `String.codePoints()`. Identical normalized vocabulary terms occur once.
If expansions tie for maximum document score, the first in this order is selected for
Explain.

The initial implementation may use a bounded vocabulary scan behind an internal
`FuzzyTermExpander`; future trie or automaton optimization cannot change these semantics.
