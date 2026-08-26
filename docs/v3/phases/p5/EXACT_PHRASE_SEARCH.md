# V3 Phase 5 exact phrase search contract

## Status

This contract is implemented and validated. Phase 5 is complete.

Phase 0 ranked-search and positional semantics, Phase 1 positioned analysis, Phase 2
positional storage, the Phase 3 snapshot-bound search pipeline, the completed Phase 4
recursive composition contract, and the V3 API compatibility contract remain
authoritative. This document resolves Phase 5-specific planning, visibility, matching,
scoring, and failure precedence without changing those earlier supported contracts.

## Delivery boundary

Phase 5 implements execution for the public query shape already frozen in Phase 0:

```java
SearchQueries.phrase(textField, text)
```

PHRASE becomes one ranked leaf in the existing recursive TEXT/BOOL/BOOST execution
tree. It may be nested under BOOL and BOOST and composed with leaves from different
fields. V3.0 phrase matching is exact relative-position matching with slop zero.

Phase 5 adds no supported phrase API, query-tree accessor, plan type, position API,
phrase bonus, phrase frequency, proximity scoring, slop, fuzzy phrase, synonym
dictionary, offsets, highlighting, Explain execution, or unrelated refactoring. FUZZY
remains unsupported until Phase 6.

## Canonical internal architecture

The Phase 3 pipeline remains the only ranked execution path:

```text
SearchRequest / frozen V2 RankedSearchRequest
    -> normalized ranked tree
    -> SearchPlanner
    -> immutable snapshot-bound SearchPlan
    -> recursive scoring plan
    -> SearchExecutor
    -> SearchResult / legacy hit list
```

The normalized tree gains an immutable package-private PHRASE equivalent:

```text
Phrase(TextField<T>, ordered slots, ordered distinct scoring terms, text index)
```

Each slot owns one normalized relative logical position and one or more distinct term
alternatives in Analyzer encounter order. The prepared scoring tree gains a
package-private `PhrasePlan` equivalent alongside `TextPlan`, `BoolPlan`, and
`BoostPlan`. It owns prepared postings, slot candidate bitmaps, the root phrase
candidate bitmap, a deterministic anchor slot, field-local BM25 facts, and immutable
logical scoring order.

Top-level engine code and `SearchExecutor` do not gain phrase-specific branches. The
phrase plan supplies a safe candidate bitmap and exact `ScoreMatch` evaluation through
the same recursive node contract as every other ranked node.

## Internal positional access boundary

Phase 2 deliberately keeps `IntPositions` and `PostingList.positions(int)`
package-private in `io.github.patricklfdm.generalsearch.index.text`. Phase 5 planning
and scoring remain package-private in `io.github.patricklfdm.generalsearch.search`, so
ordinary Java visibility cannot perform exact matching directly.

Phase 5 permits one narrow bytecode-public bridge in the text-index implementation
package, conceptually named `PhrasePositionAccess`. It is:

- `final`, non-instantiable, Javadoc-hidden, and explicitly unsupported;
- callable only with already-prepared slot-relative positions, alternative postings,
  a deterministic anchor, and one internal document ID;
- responsible only for returning exact phrase match truth;
- forbidden from analyzing text, resolving indexes or terms, building candidates,
  computing scores, or retaining request state; and
- forbidden from returning `IntPositions`, raw arrays, position collections,
  iterators, streams, callbacks that reveal positions, or any mutable/retained handle.

The bridge validates public-call boundary arguments defensively, but the normal search
path prepares immutable inputs once and performs no per-document boxing or collection
construction. `IntPositions`, its backing storage, and package-private posting reads
remain internal. No method is added to supported `PostingList`, `TextIndexSnapshot`,
or application query APIs.

This bridge is a package-layout accommodation, not a supported positional SPI. The
existing `SearchExecutionAccess` continues to expose complete request execution only;
neither bridge exposes query nodes, plans, snapshots, candidate bitmaps, score state,
or raw document positions.

## Query occurrences and deterministic traversal

Every PHRASE node occurrence is semantically independent. Reusing the same
`SearchQuery<T>` object in two clause positions causes two visits, two Analyzer calls,
two normalized leaves, two prepared plans, and two scoring contributions when both
clauses contribute. Object identity or structural equality must not memoize or merge
occurrences.

The Phase 4 logical traversal remains:

```text
BOOL:    every MUST child in encounter order, then every SHOULD child
BOOST:   its child in place
TEXT:    the occurrence itself
PHRASE:  the occurrence itself
```

Within one PHRASE leaf, only same-slot alternatives and scoring terms have the local
deduplication described below. Equal terms or equal phrases in separate leaves remain
independent.

## Whole-tree preflight and failure precedence

One invocation follows this order:

```text
1. null-check public engine/searcher arguments
2. traverse and validate the complete public ranked-query shape
3. normalize and prepare occurrences in deterministic logical depth-first order
4. if the whole tree has no non-empty TEXT or PHRASE leaf, return empty
5. finish recursive ranked candidate composition
6. plan the optional structured filter against the same snapshot
7. intersect safe ranked/filter candidates and execute the immutable plan
```

Step 2 performs no Analyzer, text-index, position, or structured-filter work. It accepts
TEXT, PHRASE, BOOL, and BOOST. A FUZZY node anywhere in the tree throws a clear
`UnsupportedOperationException` before any such work, including when an earlier
sibling would later be match-none. Construction-time null, empty-BOOL, and boost-value
validation remains unchanged.

Step 3 compiles every occurrence even when an earlier MUST is match-none or has empty
candidates. It never skips a later Analyzer failure, missing non-empty canonical index,
or unknown term preparation because of match short-circuiting. Analyzer and index
failures therefore follow the frozen logical traversal order.

If at least one non-empty ranked leaf exists, structured-filter planning occurs after
ranked preparation even when the root ranked candidate bitmap is empty. If all TEXT and
PHRASE leaves are empty after valid analysis, the request returns empty before index
resolution and filter planning.

## Positioned phrase analysis and validation

Every V3 PHRASE occurrence calls its canonical field's
`Analyzer.analyzeWithPositions(String)` exactly once. Analyzer-thrown exceptions
propagate unchanged. Before normalized slots or scoring terms are committed, the whole
returned sequence is validated according to the Phase 2 contract:

- the list is non-null;
- every element is non-null;
- every term is already non-null and non-empty by `AnalyzedToken` construction;
- the first position increment is at least one;
- later increments are non-negative; and
- logical-position accumulation from initial `-1` does not overflow `int`.

Contextual validation failures are `IllegalArgumentException`s naming the field and
token context. Invalid output is never repaired or partially consumed.

For valid output, logical positions are accumulated in Analyzer encounter order. The
first occupied logical position is subtracted from every token position so the first
slot has relative position zero. Initial gaps are validated and normalized away;
subsequent gaps remain exact and significant.

Tokens at the same logical position form one slot. Alternatives within that slot are
deduplicated in first-encounter order. The same term at different logical positions is
retained in every corresponding slot. Consequently repeated phrase terms remain
significant for matching.

Independently, one ordered scoring-term list is formed by deduplicating every analyzed
term across the leaf in global Analyzer first-encounter order.

## Empty and single-slot phrases

A zero-token PHRASE has no occupied slots and is match-none:

```text
candidates = empty
matched(docId) = false
score(docId) = 0.0
text index required = no
```

Valid text that analyzes to zero tokens is not an error. An empty PHRASE nested under
BOOL or BOOST follows ordinary recursive match-none semantics.

A phrase with one occupied slot is valid. It matches a document containing at least
one slot alternative. Its score equals the corresponding TEXT leaf produced by the
same positioned analysis: every distinct analyzed term occurring in the document
contributes once in first-encounter order.

## Canonical index resolution

Every non-empty PHRASE occurrence immediately resolves the identity-equal canonical
`TextIndexSnapshot` for its exact `TextField<T>`. A missing index throws the existing
contextual `IllegalStateException` naming the field. There is no scan fallback and a
missing SHOULD index is not silently ignored.

The canonical index is required even when every analyzed term is unknown. Unknown
terms resolve to ordinary empty postings and produce empty slot/root candidates rather
than a planning error. An empty PHRASE is the only phrase leaf that requires no index.

## Phrase candidate construction

For each slot, planning resolves every distinct alternative posting once and builds:

```text
slotCandidates = union(posting(term).documents() for every slot alternative)
```

The phrase candidate bitmap is:

```text
phraseCandidates = intersection(slotCandidates for every occupied slot)
```

This bitmap is an immutable request-level safe superset. Exact positional verification
may reject false positives; false negatives are forbidden. A slot containing only
unknown alternatives makes the phrase candidate bitmap empty.

Repeated term sources across different slots, or structurally equal slot candidate
sources, may be physically intersected once where safe. This optimization never
removes repeated slots from exact verification or scoring occurrences. Slot
intersections may run in ascending cardinality order with original slot order as the
deterministic physical tie-break. Physical order never changes stored logical slot or
scoring-term order.

## Deterministic anchor selection

The exact verifier anchors on the occupied slot whose fully unioned slot candidate
bitmap has the lowest cardinality. Ties select the earliest phrase slot. It does not
select an individual alternative by minimum document frequency because that would not
represent the complete OR slot.

Within the chosen slot, alternative postings are visited in frozen Analyzer order and
their stored positions in ascending order. The same logical anchor position reached
through multiple distinct alternatives may be checked more than once; correctness and
determinism do not require a per-document boxed deduplication set. Anchor selection is
prepared once and does not change BM25 accumulation order.

## Exact relative-position verification

For anchor slot relative position `qa`, one stored anchor document position `da`, and
another slot relative position `qs`, the required document position is computed as:

```text
required = (long) da + ((long) qs - (long) qa)
```

If `required` is negative or exceeds `Integer.MAX_VALUE`, that anchor occurrence cannot
match and is rejected without throwing. Otherwise the other slot matches when at least
one of its prepared alternative postings contains `required` for the same document.
The document matches the phrase when one anchor occurrence satisfies every slot.

The verifier uses only Phase 2 stored sorted primitive positions. It performs binary
search/`contains`-style lookup and anchor iteration inside the internal positional
bridge. It never re-analyzes document text, scans all documents, allocates boxed
position collections per candidate, or builds a second phrase-specific position index.

Position gaps must match exactly. Repeated terms must occur at each required relative
position. A phrase may begin at any non-negative document position. Same-position query
alternatives are OR choices for one slot and never become multiple required positions.

## Phrase BM25 scoring

Exact positional truth is a match gate. PHRASE adds no implicit bonus:

```text
if exact phrase does not match:
    ScoreMatch(false, 0.0)

if exact phrase matches:
    ScoreMatch(true, ordered sum of ordinary BM25 term contributions)
```

After a match, each distinct analyzed phrase term that occurs anywhere in the same
field/document contributes ordinary BM25 exactly once in global Analyzer
first-encounter order. Repeated occurrences of the same query term in different slots
remain required for match truth but do not multiply query weight.

Same-position alternatives follow that rule without a second interpretation. If
`usa` and `united_states` are distinct analyzed query terms and both occur in the
document, both contribute once after the phrase matches, even when either alternative
alone could satisfy their slot. If only one occurs, only that term contributes.
Scoring is not limited to whichever alternative first proved the positional match.

Every term uses its phrase field's own prepared posting, `N`, `df`, `dl`, `avgdl`, and
the request's `Bm25Config`. Document length remains emitted analyzed-token count;
position gaps do not increase it. IDF and other request-level facts are computed once,
not per candidate document.

Phrase scoring reuses Phase 4 `ScoreMatch` and checked arithmetic. Match truth is not
inferred from `score > 0.0`. Each term addition occurs immediately in frozen scoring
order. NaN, infinity, or negative results throw `ArithmeticException`; valid positive
underflow is canonicalized to `+0.0`, and a matched zero-score phrase remains eligible.

## Recursive composition, filters, and ordering

PHRASE candidates and exact evaluation compose through the unchanged recursive BOOL
and BOOST rules. BOOST preserves phrase match truth and checked-multiplies its score.
BOOL adds matching child scores in the frozen MUST-then-SHOULD logical order. Leaves in
different fields retain independent statistics; Phase 5 adds no BM25F, DisMax,
coordination factor, field normalization, or implicit phrase weight.

`SearchRequest.filter(Query<T>)` remains eligibility-only. It is planned against the
same immutable request snapshot after ranked preparation and contributes zero score.
Surviving documents retain the same phrase score with or without an equivalent
permissive filter.

Final results retain at most `limit` matched documents and sort by score descending,
then internal document ID ascending. Physical anchor or bitmap order cannot influence
logical score order or final tie-breaking.

## Snapshot, mutation, and dynamic-index behavior

Every phrase plan is bound to the one immutable `SearchSnapshot<T>` captured for the
request. Documents, positional postings, lengths, statistics, candidates, and filters
come from that exact snapshot. Concurrent publication cannot mix old and new phrase
facts within one invocation, and an old snapshot retains its old positional truth.

Existing add, update, remove, bulk mutation, asynchronous publication, dynamic index
build/replay, publication, and drop behavior remains authoritative. Reordering tokens
with unchanged frequencies changes phrase truth after successful publication. Dynamic
text indexes must expose replay-correct positions to phrase planning when published;
after drop, a non-empty phrase on that canonical field fails as a missing index.

Phase 5 changes neither writer concurrency nor snapshot publication and adds no public
snapshot API for testing.

## Compatibility and public surface

All published 1.0.0, 2.0.0, and 2.1.0 descriptors and behaviors remain supported.
`SearchQueries.phrase(...)` was already added in Phase 0; Phase 5 only implements its
built-in execution. Third-party `SearchEngine` implementations retain default
unsupported V3 capabilities.

The V2 `searchTopK`, `RankedSearchRequest`, `TextScoringQuery`, direct
`RankedSearcher`, frozen terms, filters, scores, ordering, and failure precedence remain
unchanged. V2 input never manufactures a PHRASE and never re-analyzes query text.

Phase 5 adds no supported public class or method. Japicmp may report the Javadoc-hidden
`PhrasePositionAccess` as one additive bytecode-public class, just as it reports the
Phase 3 execution bridge. It carries no application compatibility guarantee and is not
a supported position API. Source/reflection fixtures and independent v1-, v2-, and
v3-style consumers remain mandatory.

## Required verification

Focused tests must cover:

- empty, single-slot, adjacent, reordered, gapped, repeated-term, and unknown-term
  phrases;
- same-position alternative matching, within-slot deduplication, and the exact case
  where multiple distinct alternatives occur and score;
- whole-tree FUZZY preflight before Analyzer, index, position, or filter work;
- complete positioned-output validation, per-occurrence Analyzer call counts, reused
  query objects, deterministic traversal, and missing-index precedence;
- all-empty TEXT/PHRASE trees, empty phrase without an index, later missing SHOULD
  indexes after match-none MUST leaves, and filter-planning precedence;
- slot-union/phrase-intersection candidate-superset safety, deterministic anchor
  selection, anchor ties, and relative-position arithmetic boundaries;
- exact BM25 scores, field-local statistics, checked addition/multiplication,
  matched-zero retention, BOOL/BOOST/cross-field composition, and structured filters;
- add/update/reorder/remove/bulk behavior, old-snapshot isolation, concurrent
  publication, and dynamic text-index build/replay/drop;
- direct TEXT, recursive Phase 4, V2 legacy, fuzzy-unsupported, and Explain-unsupported
  regressions; and
- deterministic randomized differential comparison of match truth, score, order, and
  candidate-superset safety against a trusted positioned reference evaluator.

The internal bridge must be inspected to prove it exposes no `IntPositions`, raw
position array/collection/iterator/stream/callback, query node, plan, snapshot, bitmap,
score state, or internal position handle.

A focused phrase JMH or equivalent repeatable smoke records environment and workload
and demonstrates no obvious full-document scan, document reanalysis, per-document
posting/index/IDF resolution, per-document slot/candidate reconstruction, boxed
position collection, or unbounded hit retention. Phase 5 freezes no numeric release
threshold or universal speedup claim.

The full reactor, travel example, source/reflection fixture, normal and isolated
artifact compatibility, independent consumers, strict Javadocs, release packaging,
artifact inspection, reproducibility, JMH compilation, and version-alignment gates
remain mandatory.

## Completion rule

Phase 5 is complete only when every checklist item passes, roadmap and changelog status
accurately describe the implementation, performance evidence is recorded, and no Phase
6+ behavior or unsupported position surface has been added.
