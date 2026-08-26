# V3 Phase 6 single-term fuzzy search contract

## Status

This contract is implemented and validated. Phase 6 is complete.

The Phase 0 fuzzy semantics and ranked-search contracts, Phase 1 positioned analysis,
Phase 2 positional text storage, Phase 3 snapshot-bound pipeline, Phase 4 recursive
composition, Phase 5 exact phrase execution, and V3 compatibility policy remain
authoritative. This document resolves Phase 6-specific visibility, validation,
expansion, scoring, lifecycle, and failure precedence.

## Delivery boundary

Phase 6 implements the existing public query shape:

```java
SearchQueries.fuzzy(textField, text)
```

FUZZY is one ranked leaf in the existing TEXT/PHRASE/BOOL/BOOST tree. It represents
exactly one emitted analyzed token and expands that normalized term against the
canonical field-local vocabulary. It adds no new supported public fuzzy API.

Phase 6 does not implement automatic multi-token fuzzy, fuzzy phrase, spelling
correction, suggestions, public fuzziness controls, expansion truncation, prefix
length, stemming, synonyms, a persistent fuzzy dictionary, Explain, phrase slop, or
other Phase 7+ behavior.

## Canonical architecture

The only execution path remains:

```text
SearchRequest
    -> deterministic normalized ranked tree
    -> SearchPlanner
    -> immutable snapshot-bound SearchPlan
    -> recursive scoring node
    -> SearchExecutor
    -> SearchResult
```

The normalized tree gains a package-private FUZZY node containing the canonical
`TextField`, zero or one normalized query term, and the identity-equal text-index
snapshot when non-empty. The prepared scoring tree gains a package-private
`FuzzyPlan`. Top-level engine and executor code gain no fuzzy-specific branch.

A package-private `FuzzyTermExpander` abstraction owns expansion semantics. Its first
implementation performs one bounded scan of the immutable snapshot vocabulary during
planning. A future trie or automaton may replace that implementation only if it
produces the identical frozen expansion set and order.

## Internal vocabulary visibility boundary

`TextIndexSnapshot` deliberately keeps its `PersistentAvlMap<String, PostingList>`
package-private in `io.github.patricklfdm.generalsearch.index.text`, while the fuzzy
expander and planner remain package-private in
`io.github.patricklfdm.generalsearch.search`.

Phase 6 permits one narrow bytecode-public bridge, conceptually named
`FuzzyVocabularyAccess`, in the text-index implementation package. It is final,
non-instantiable, stateless, Javadoc-hidden, and explicitly unsupported. Its only
operation synchronously visits each normalized vocabulary term from one supplied
`TextIndexSnapshot` exactly once. It may accept a standard `Consumer<String>` but:

- returns no vocabulary collection, posting, bitmap, position, index dictionary,
  iterator, stream, snapshot handle, expansion, plan, score, or internal document ID;
- performs no query analysis, edit distance, expansion filtering, candidate building,
  or scoring;
- retains neither the snapshot nor callback; and
- adds no method to supported `TextIndexSnapshot`, `PostingList`, or query APIs.

The expander explicitly sorts accepted expansions by the frozen code-point order; it
does not rely on the AVL map's UTF-16 `String.compareTo` traversal order. No reflection,
duplicate dictionary, or second Phase 6 visibility bridge is permitted.

Japicmp may report this bridge as one additive bytecode-public class. Compatibility
review must confirm that exact hidden boundary. The class is not a supported
application vocabulary SPI.

## Whole-tree validation and deterministic traversal

One request follows this order:

```text
1. null-check public engine/searcher arguments
2. preflight the complete public ranked-query shape without Analyzer/index/filter work
3. normalize every leaf occurrence in MUST-then-SHOULD depth-first order
4. if every TEXT/PHRASE/FUZZY leaf is empty, return empty before index/filter planning
5. prepare every recursive scoring leaf and compose ranked candidates
6. plan the optional structured filter against the same snapshot
7. execute exact prepared scoring with bounded top-K retention
```

Phase 6 preflight accepts TEXT, PHRASE, FUZZY, BOOL, and BOOST. It still rejects unknown
internal shapes. Every occurrence is independent: reusing one fuzzy query object in
two clauses performs two Analyzer calls, two expansions, and two scoring contributions.
There is no identity or structural memoization.

Normalization and planning do not short-circuit later occurrences after an earlier
empty, invalid, missing, or empty-candidate leaf except by throwing the first failure
in logical traversal order. An empty-candidate non-empty fuzzy leaf does not suppress a
later Analyzer or missing-index failure. When at least one ranked leaf is non-empty,
filter planning still occurs even if recursive ranked candidates become empty.

## Canonical fuzzy analysis

Every FUZZY occurrence calls its field's `Analyzer.analyzeWithPositions(String)`
exactly once. Analyzer-thrown exceptions propagate unchanged. The complete returned
sequence is validated before fuzzy cardinality is decided:

- the list and every element are non-null;
- the first position increment is positive;
- later increments are non-negative; and
- logical-position accumulation from `-1` uses checked `int` arithmetic.

Validation failures are contextual `IllegalArgumentException`s naming the field and
token context, consistent with TEXT and PHRASE normalization.

Cardinality means emitted token occurrences, not distinct term count and not occupied
position count:

```text
0 emitted tokens -> match-none
1 emitted token  -> valid normalized fuzzy term
2+ emitted tokens -> IllegalArgumentException
```

Two equal emitted terms or two same-position alternatives still count as two and are
rejected. Phase 6 never silently chooses or deduplicates one token from multi-token
analysis.

A zero-token FUZZY requires no text index, performs no vocabulary traversal, and owns
empty candidates with zero score. Every non-empty FUZZY immediately resolves the
identity-equal canonical `TextIndexSnapshot`; a missing index throws the existing
contextual `IllegalStateException` before expansion or filter planning.

## AUTO edit threshold and Unicode domain

AUTO uses the normalized query term's Unicode code-point count:

| Query code-point length | Maximum edits |
|---:|---:|
| 1–2 | 0 |
| 3–5 | 1 |
| 6+ | 2 |

Indexed terms and valid analyzed query terms are non-empty. The maximum is always two.
UTF-16 code-unit length, locale, collation, grapheme clusters, normalization forms,
and case folding do not define distance; any normalization is the Analyzer's job.

## Bounded Optimal String Alignment distance

Production distance is bounded Optimal String Alignment over arrays of Unicode code
points. Insertion, deletion, substitution, and adjacent transposition each cost one,
and no substring may be edited more than once. This is the Phase 0 OSA definition, not
unrestricted Damerau-Levenshtein and not plain Levenshtein.

The internal operation accepts only a bound from zero through two. It returns the exact
distance when within the bound and a single out-of-range sentinel otherwise. Length
difference greater than the bound is rejected before dynamic programming. A banded
primitive-array implementation may use only correctness-safe early exits; it allocates
no full boxed matrix per comparison.

Deterministic randomized tests compare it to a simple full-matrix OSA reference over
ASCII and supplementary code points for bounds zero, one, and two.

## Exact expansion set and order

For normalized query `q` and AUTO bound `k`:

```text
E(q) = { t in the canonical snapshot vocabulary | OSA(q, t) <= k }
```

Every valid vocabulary term is included exactly once. There is no hidden
`maxExpansions`, early truncation, document-frequency cutoff, prefix heuristic, or
approximation. A bound of zero may use direct exact lookup rather than scan, provided
the observable expansion is identical.

The immutable expansion order is:

1. edit distance ascending;
2. lexicographic comparison of the numeric sequence returned by `String.codePoints()`.

The second rule is not Java UTF-16 `String.compareTo` for supplementary characters.
Each prepared expansion owns its normalized term, posting, edit distance, code-point
length, similarity, and expansion-specific IDF. Posting lookup, distance, similarity,
IDF, document count, and average field length are prepared once per leaf, never per
candidate document.

## Candidates

The fuzzy candidate bitmap is the union of every expansion posting bitmap. It is exact
for the leaf: a document matches iff at least one prepared expansion has positive term
frequency. No document text or per-document vocabulary is scanned. No edit distance is
computed during document evaluation.

No expansion produces empty candidates and a normal match-none plan; it is not an
error. Recursive BOOL and structured-filter candidate composition remain unchanged.

## Frozen fuzzy scoring

Every expansion uses the fuzzy field's own `N`, expansion `df`, document `tf`, field
document length, average field length, and request `Bm25Config`.

If the exact normalized query posting has positive term frequency in a candidate
document, the leaf score is that exact term's ordinary BM25. All other expansions are
ignored for that document even if one would have a larger weighted score or the exact
score underflows to zero.

Otherwise each matching non-exact expansion has:

```text
similarity(q, t) = 1 - distance(q, t)
                         / max(codePointLength(q), codePointLength(t))

weightedScore(t, d) = BM25(t, d) * similarity(q, t)
```

Floating-point division is used. Similarity and every BM25/intermediate/multiplication
are required to be finite and non-negative. Arithmetic is checked immediately in the
frozen operation order. Valid underflow is canonical matched `+0.0`.

The fuzzy leaf score is the maximum matching weighted score, never a sum. Expansions
are evaluated in their frozen order and the current selection is replaced only by a
strictly greater score. Exact `Double.compare` equality therefore retains the first
expansion: lower edit distance, then code-point lexicographically smaller term. This
selected term remains internal until Phase 7 Explain.

Match truth is independent from score positivity. A matching zero-score fuzzy leaf is
retained and composes through existing checked BOOL addition and BOOST multiplication.

## Composition, filters, and ordering

FUZZY uses the unchanged recursive scoring contract under MUST, SHOULD, nested BOOL,
and nested BOOST. TEXT and PHRASE behavior is unchanged. Cross-field leaves use wholly
independent canonical indexes and field-local statistics. There is no BM25F, DisMax,
coordination factor, implicit fuzzy boost, or multi-field fuzzy leaf.

Structured filters remain eligibility-only and contribute zero score. Final results
remain score descending, then internal document ID ascending, with bounded top-K
retention including matched zero scores.

## Snapshot and dynamic-index lifecycle

Every fuzzy normalization, vocabulary scan, posting, statistic, candidate, filter, and
document read belongs to exactly one immutable `SearchSnapshot`. Publication during
analysis or execution cannot mix versions. Old snapshots preserve their old vocabulary,
postings, truth, and scores.

Add, update, remove, reorder, and bulk publication update fuzzy truth and ranking.
Dynamic text-index creation must scan the replay-correct published vocabulary after
pending mutations are replayed. Dropping the canonical index makes a later non-empty
fuzzy request fail with the normal missing-index error.

## Testing and performance evidence

Focused tests cover analysis cardinality and validation, all AUTO boundaries, every
edit operation, supplementary code points, exact expansion sets/order, exact-term
priority, max-not-sum scoring, tie retention, expansion-specific BM25, custom BM25,
checked arithmetic, BOOL/BOOST/cross-field/filter composition, missing indexes, stable
result ordering, mutation, snapshot isolation, and dynamic build/replay/drop.

Three deterministic differentials are mandatory:

- bounded production OSA versus full reference OSA;
- production expansion versus brute-force reference vocabulary expansion; and
- end-to-end fuzzy match/score/order versus a reference evaluator across mutations,
  composition, filters, boosts, and BM25 configurations.

A focused JMH case records vocabulary-scan planning plus top-K execution at more than
one vocabulary size and a composed fuzzy workload. It is diagnostic only, establishes
no numeric release threshold, and makes no universal speedup claim. Inspection must
confirm there is no per-document analysis, vocabulary scan, edit distance, IDF
preparation, or unbounded hit retention.

## Compatibility and non-goals

The independent V3 consumer gains executable single-term fuzzy usage through the
existing public façade. V1 and V2 consumers and legacy `searchTopK` remain unchanged.
Normal and isolated Japicmp comparisons against 1.0.0, 2.0.0, and 2.1.0 remain
mandatory, as do source/reflection fixtures, strict Javadocs, release artifacts, and
reproducibility.

Phase 6 adds no supported public type, method, field, constructor, record component, or
descriptor. The one hidden vocabulary bridge is the only bytecode-public addition.
`SearchExecutionAccess` and `PhrasePositionAccess` remain otherwise unchanged. Explain
continues to throw its existing unsupported failure.

## Completion rule

Phase 6 is complete only when the implementation matches this contract, every item in
`PHASE_6_CHECKLIST.md` passes, the roadmap/changelog/phase map are updated, the root
prompt remains untracked, and all correctness, compatibility, consumer, Javadoc,
release, reproducibility, and performance-smoke gates pass. Phase 7+ behavior is scope
failure, not extra progress.
