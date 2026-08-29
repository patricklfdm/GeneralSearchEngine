# V3.1 validation contract

## Independent oracles

New execution paths are validated against independent, representation-free oracles:

- phrase oracle analyzes the query and document into logical positions, enumerates
  ordered slot witnesses, computes consumed extra-gap slop with overflow-safe `long`
  arithmetic, and does not call posting or phrase-plan code;
- BOOL oracle recursively evaluates every declared clause occurrence, applies the
  frozen effective minimum, and sums scores in logical builder order;
- fuzzy oracle traverses the complete sorted vocabulary and uses the existing bounded
  OSA reference calculation, never the trie or trie-pruning state;
- top-K oracle exhaustively collects all matches and full-sorts by score descending
  then internal insertion order for test fixtures.

Randomized tests compare match truth, score bits or the existing accepted floating
comparison rule, hit order, and Explain match/score. A shared implementation helper
cannot serve as both production logic and its oracle.

## Phrase matrix

Focused phrase fixtures include:

| Shape | Required observations |
|---|---|
| exact and explicit zero | old and new factories return identical hits, score, order, failures, and Explain |
| extra gaps | consumed slop immediately below, equal to, and above the requested bound |
| contraction | document gaps smaller than analyzed query gaps do not match |
| transposition | reordered terms do not match at any slop |
| repeated term | one occurrence cannot satisfy multiple ordered slots |
| same-position alternatives | either alternative satisfies one slot without extra slop |
| analyzer gaps | initial gap normalizes away; internal gaps remain minimum gaps |
| one slot and empty output | one slot consumes zero; empty output matches nothing before index resolution |
| nested BOOL/BOOST/filter | phrase match composes without hidden score or eligibility changes |
| arithmetic boundary | large logical positions fail during analysis or compare safely without wraparound |

The randomized generator varies slot count, alternatives, repeated terms, increments,
document positions, slop, boosts, structured filters, index presence, and mutation
history. Exact and sloppy paths run against indexed snapshots only; the independent
oracle reads source documents.

## BOOL threshold matrix

Focused BOOL fixtures cover:

- unset minimum with and without MUST;
- explicit zero with MUST and rejection without MUST;
- negative value and value above declared SHOULD count;
- minimum `1`, intermediate, and all;
- duplicate SHOULD occurrences and the same child in MUST and SHOULD;
- zero-term, matched-zero-score, boosted, phrase, fuzzy, and nested BOOL children;
- conservative candidate supersets versus full logical evaluation;
- structured filter pass/fail and all failure-precedence combinations;
- Explain effective minimum, matched occurrence count, child order, match, and score.

The randomized oracle retains occurrence identity and never deduplicates clauses.
Meeting the threshold cannot stop score accumulation.

## Fuzzy trie matrix

Exhaustive small-alphabet tests enumerate query and vocabulary strings through the
supported maximum length and edit bound, including adjacent transposition. Randomized
tests add supplementary Unicode code points, unequal UTF-16/code-point lengths, prefix
sharing, long terms, exact terms, empty expansions, and deterministic ordering.

For every snapshot, trie visitation must equal full scan in accepted term set and
distance. Search then compares expansion order, candidate union, exact priority,
selected max score, tie-breaking, hit order, and Explain.

Lifecycle fixtures cover:

- first document introducing a term;
- posting updates that retain vocabulary membership;
- final document removing a term;
- remove then re-add in one bulk publication;
- failed or rolled-back bulk mutation;
- dynamic text-index build with journal replay;
- build cancellation, drop, close, and analysis failure;
- concurrent reads across old and new snapshots;
- structural-sharing identity checks limited to internal tests.

## Compatibility and visibility

Reflection/descriptor tests confirm the supported V3.1 additions and the absence of a
public query-node, trie, posting, position, candidate, plan, snapshot, or internal-ID
handle. Existing bridge visibility tests are extended only for the contract-authorized
methods. The V3-style independent consumer exercises both new APIs; V1 and V2
consumers remain source-unchanged.

## Performance correctness guards

Every benchmark consumes results and asserts stable cardinality/checksum facts outside
the timed path where JMH permits. Trie benchmarks verify expansion identity against a
setup-time full-scan oracle. Phrase benchmarks include exact-zero equivalence and
sloppy-match counts. Concurrent and soak runners retain zero-error, queue, cleanup,
document-count, and final differential-oracle gates.
