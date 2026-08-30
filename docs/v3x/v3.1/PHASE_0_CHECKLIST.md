# V3.1 Phase 0 checklist

Status: contract freeze complete; production implementation has not started.

## Frozen decisions

- [x] V3.1 keeps the V3.0 in-memory snapshot and writer architecture.
- [x] Phrase slop uses an ordered extra-gap budget and does not permit transposition.
- [x] Slop changes match truth only; phrase scoring remains distinct-term BM25.
- [x] Existing two-argument phrase queries remain exactly slop zero.
- [x] Unspecified BOOL minimum preserves V3.0 behavior.
- [x] Explicit BOOL minimum validation, duplicate occurrence counting, zero-term
  behavior, nested behavior, score order, and Explain facts are frozen.
- [x] Ranked `mustNot` and pure-negative BOOL are outside V3.1.
- [x] Public fuzzy controls and expansion caps are outside V3.1.
- [x] Fuzzy optimization uses a persistent code-point trie with exact bounded OSA
  traversal and the full scan as a differential oracle.
- [x] Regression and V3.1 feature benchmark identities remain separate.
- [x] Phrase, BOOL, fuzzy, lifecycle, compatibility, and benchmark oracle/fixture
  matrices are frozen.
- [x] The bounded `ranked-v31` / `v3.1-ranked-v1` protected cloud extension is frozen.
- [x] Six-hour and longer soak requires a later Cloud Benchmark contract extension.

## Frozen public surface

- [x] The only supported additions are the phrase factory overload and
  `BoolBuilder.minimumShouldMatch(int)`.
- [x] `Analyzer` remains a SAM and `AnalyzedToken` remains unchanged.
- [x] No query node, position, trie, vocabulary, posting, plan, candidate, snapshot, or
  internal document-ID type becomes supported API.
- [x] Allowed hidden bridge changes are bounded and documented.

## Implementation entry gates

The first three gates were completed by Phase 1. The protected cloud extension
remains a later implementation phase:

- [x] Add direct Japicmp comparison with published `3.0.0` while retaining all older
  comparisons.
- [x] Capture focused pre-change phrase and fuzzy profiles from the unmodified V3.0
  implementation.
- [x] Materialize the independent Phase 1 phrase/BOOL reference models and focused
  V3.0-default fixtures without sharing production implementation helpers. The full
  feature matrix remains an implementation exit gate.
- [x] Implement and synthetically validate the frozen `ranked-v31` cloud extension
  before any paid run.

## Implementation exit gates

- [ ] Focused unit tests cover every validation and failure-precedence rule.
- [ ] Randomized phrase and BOOL differential tests pass against independent oracles.
- [x] Fuzzy trie traversal passes exhaustive and randomized full-scan equivalence.
- [ ] Search and Explain match/score invariants pass for all new shapes.
- [ ] Mutation, bulk, snapshot, dynamic-index, concurrency, and close lifecycle tests
  pass.
- [ ] V1, V2, V3.0, processor, generated, and independent consumer gates pass.
- [ ] Strict Javadocs, release artifacts, and reproducible builds pass.
- [ ] Frozen regression-lane and distinct feature-lane evidence is reviewed.

No production Java, benchmark runner, workflow, or release-version change belongs in
Phase 0. Implementation starts only from these frozen contracts and records any needed
contract amendment before changing behavior.
