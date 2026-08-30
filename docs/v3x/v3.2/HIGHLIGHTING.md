# V3.2 structured highlighting semantics

Highlighting is an opt-in snapshot-bound presentation result over an existing ranked
search. It never inserts HTML and never changes retrieval semantics.

## Public request and result family

V3.2 adds final immutable types under the existing search package:

```text
HighlightedSearchRequest<T>
HighlightedSearchResult<T>
HighlightedSearchHit<T>
FieldHighlight
HighlightFragment
HighlightSpan
```

The engine gains one additive default capability:

```java
default HighlightedSearchResult<T> search(
        HighlightedSearchRequest<T> request
)
```

The default checks a non-null request and throws `UnsupportedOperationException`,
preserving binary compatibility for third-party `SearchEngine` implementations. The
built-in engine overrides it.

`HighlightedSearchRequest<T>` wraps one immutable `SearchRequest<T>` and is built with:

```java
HighlightedSearchRequest.<T>builder(searchRequest)
        .field(textField)
        .contextCharacters(40)
        .maxFragmentsPerField(3)
        .build();
```

The defaults are 40 UTF-16 context units on each side and at most three fragments per
field. At least one field is required. Field order is insertion order; duplicate
logical field names are rejected. Context may be zero and the fragment cap must be
positive. Builders are mutable and not thread-safe; built requests are immutable
snapshots.

The result model is:

```text
HighlightedSearchResult.hits()
  -> ordered List<HighlightedSearchHit<T>>

HighlightedSearchHit.hit()
  -> the canonical SearchHit<T>

HighlightedSearchHit.highlights()
  -> requested fields that produced at least one span

FieldHighlight.fieldName()
FieldHighlight.fragments()

HighlightFragment.startOffset()
HighlightFragment.endOffset()
HighlightFragment.text()
HighlightFragment.spans()

HighlightSpan.startOffset()
HighlightSpan.endOffset()
```

All lists are immutable defensive copies. Fragment and span offsets are absolute
half-open UTF-16 ranges into the original field string. Fragment text equals the exact
`source.substring(startOffset, endOffset)`. Every span is contained by its fragment;
consumers subtract the fragment start when applying markup to fragment text.

Public result constructors enforce their context-free invariants. Lists, elements,
hit, field name, and fragment text are non-null. Field names are non-empty and unique
within a hit. A `FieldHighlight` contains at least one fragment; a fragment contains at
least one span. Span and fragment ranges are non-empty and non-negative. Fragment text
has exactly `endOffset - startOffset` UTF-16 units. Spans are strictly ordered,
non-overlapping, and contained by their fragment; fragments are strictly ordered and
non-overlapping within a field. Highlight fields follow request order. Empty result
hits and empty per-hit highlight lists are valid.

The first V3.2 surface intentionally returns no HTML, CSS class, formatter callback,
mutable builder node, raw normalized term, plan identity, posting, or internal document
ID. A consumer owns escaping, markup, colors, and display policy.

## Snapshot and search invariants

For request `H` wrapping search request `R`:

```text
search(H).hits().map(HighlightedSearchHit::hit)
    == search(R).hits()
```

when observed against the same immutable snapshot. Equality covers document reference,
score bits, order, cardinality, and limit. The built-in highlighted operation performs
both sides internally against one captured snapshot; this equation is a semantic
oracle, not an instruction to make two public calls.

Structured filters affect eligibility only and never create spans. Highlight options
cannot change normalization, missing-index precedence, candidates, phrase truth, fuzzy
selection, BOOL thresholds, boost arithmetic, top-K membership, or tie-breaking.

## Leaf semantics

### TEXT

A matched TEXT leaf selects every occurrence in the requested document field whose
normalized term is a matched normalized query term for that leaf. Each occurrence
initially creates its source token range. Query duplicates do not create duplicate
visible ranges.

### PHRASE

A matched PHRASE leaf selects one deterministic valid witness. Witness ordering is:

1. least consumed slop;
2. earliest first-token start offset;
3. earliest subsequent occurrence-offset tuple.

The visible phrase range begins at the first selected token's start and ends at the
last selected token's end, so intervening source whitespace, punctuation, and allowed
gaps are included. Same-position alternatives contribute the one source range for the
selected alternative. One-slot phrases use that token range.

This witness rule agrees with Explain's minimum-consumed-slop fact but does not expose
raw logical positions. Highlighting all possible phrase witnesses is intentionally not
part of V3.2; one bounded deterministic witness per matched phrase leaf avoids
combinatorial output.

### FUZZY

A matched FUZZY leaf uses the same selected expansion and tie-breaking as existing
per-document fuzzy scoring and Explain. Every occurrence of that selected normalized
term in the requested field creates a source token range. Other accepted vocabulary
expansions that did not win the document score do not create spans.

### BOOL and BOOST

BOOL emits the union of evidence from every matched MUST child and every matching
SHOULD child evaluated by the final BOOL result. Meeting `minimumShouldMatch` does not
stop SHOULD evidence collection, just as it does not stop score accumulation. A
zero-score matched child may still highlight. An unmatched child never does.

BOOST forwards the child ranges unchanged. Reusing an equal leaf in multiple clause
occurrences preserves scoring occurrence semantics but duplicate visible ranges are
deduplicated.

## Range normalization

Raw ranges are grouped by requested field and normalized before fragments are built:

1. sort by start offset, then end offset;
2. remove exact duplicates;
3. merge overlapping ranges into their half-open union;
4. keep merely adjacent non-overlapping ranges separate; and
5. retain a phrase's already-contiguous witness range as one range.

The normalized `HighlightSpan` list is therefore deterministic and strictly ordered.
It carries presentation ranges, not clause multiplicity or score contribution.

## Fragment algorithm

For each normalized span `[s, e)`, create a proposed window:

```text
[max(0, s - contextCharacters),
 min(source.length(), e + contextCharacters))
```

If a window boundary falls between a UTF-16 high/low surrogate pair, expand it outward
by one code unit. Sort proposed windows and merge overlapping windows. Do not merge
windows separated by one or more source units. Attach every contained normalized span,
then retain the earliest `maxFragmentsPerField` windows.

Fragments are ordered by absolute source position, not query-clause order or score.
No sentence/word-boundary heuristic, ellipsis, HTML escaping, locale rule, or maximum
source length is hidden in the first implementation. Later fragment-ranking or
boundary policies require additive explicit options and their own evidence.

Fields with null/empty source or no selected ranges are absent from
`HighlightedSearchHit.highlights()`. A hit with no requested-field ranges remains in
the result with an empty highlight list.

## Validation and failure precedence

Request builders fail immediately for null search request/field, negative context,
non-positive fragment cap, duplicate logical field name, or build without a field.

The built-in engine then applies this order:

1. reject null highlighted request at the public boundary;
2. reject a closed engine according to the existing read contract;
3. validate every requested `TextField` is the canonical schema-owned instance;
4. reject every requested field whose configured analyzer lacks `OffsetAnalyzer`;
5. run the wrapped SearchRequest through unchanged whole-tree and index validation;
6. execute canonical top-K on one snapshot; and
7. extract/re-analyze returned documents and validate complete offset sequences.

Capability/canonical-field failures occur even when the search would return no hits,
so unsupported behavior cannot depend on corpus contents. Query and missing-index
failure precedence within step 5 remains exactly V3.1.

Extractor or analyzer exceptions propagate according to the existing field/analysis
contract. Structurally invalid offset output is wrapped as field-specific
`IllegalArgumentException`. Any failure aborts the complete call; no partially built
hit or fragment list is returned.

## Explain relationship

Highlighting and Explain share match truth, selected fuzzy expansion, phrase
minimum-slop witness ordering, BOOL child truth, and score arithmetic. Highlight result
types do not embed `ExplanationNode`, and description strings are never parsed to
produce ranges. Tests compare both operations through independent structured oracles.

## Explicit exclusions

V3.2 highlighting does not support structured `Query` highlighting, arbitrary regex
matching, HTML rendering, custom formatter callbacks, all-witness phrase enumeration,
stored offsets, multi-token synonym graphs, completion suggestions, snippets ranked by
machine-learned quality, or cross-document fragments.
