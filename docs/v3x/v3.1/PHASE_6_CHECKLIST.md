# V3.1 Phase 6 checklist

Status: complete. Fuzzy expansion now uses a persistent Unicode-code-point trie with
exact bounded OSA traversal. Supported API and all V3.0 fuzzy semantics remain
unchanged.

## Persistent dictionary and publication

- [x] Store one package-private immutable code-point trie beside each text-index
  posting dictionary; terminals retain only the canonical normalized term.
- [x] Order every edge by numeric Unicode code point and structurally share unchanged
  nodes and paths across snapshots.
- [x] Add membership only when a posting changes from empty to non-empty and remove it
  only on the inverse transition. Posting-frequency and position-only changes reuse
  the same trie instance.
- [x] Resolve all changes against the final dirty posting state so remove/re-add in one
  publication preserves membership.
- [x] Batch path copying by common prefix for larger publications, preventing one
  discarded intermediate trie per changed term.
- [x] Publish postings, document lengths, positions, statistics, and trie membership
  atomically in one `TextIndexSnapshot`.

## Exact bounded OSA traversal

- [x] Maintain bounded dynamic-programming rows over query code points while visiting
  trie prefixes; support insertion, deletion, substitution, and adjacent
  transposition with the frozen OSA semantics.
- [x] Prune only when the complete bounded row proves that no descendant can return
  within the requested distance.
- [x] Keep traversal workspace invocation-local and visit terminals synchronously
  without exposing trie nodes, postings, snapshots, candidates, or plans.
- [x] Sort accepted expansions by edit distance and numeric-code-point term order
  before existing exact priority, candidate union, BM25 scoring, and Explain logic.
- [x] Retain the complete posting-dictionary visitor and vocabulary-scanning expander
  as differential oracles.

## Differential and lifecycle validation

- [x] Exhaustively compare all non-empty strings through length four over a
  three-code-point alphabet at bounds zero, one, and two with the independent full
  matrix OSA reference.
- [x] Compare 400 deterministic randomized vocabularies and queries containing BMP,
  private-use, and supplementary code points with both the independent reference and
  retained full scan.
- [x] Cover long shared prefixes, supplementary code points, unequal lengths,
  transposition, exact terms, empty expansion sets, and numeric-code-point ordering.
- [x] Verify first insertion, posting-only update, final removal, remove/re-add in one
  publication, and unchanged-branch object identity.
- [x] Preserve fuzzy search, scoring, candidate, Explain, mutation, old-snapshot,
  dynamic-index, concurrent-publication, drop, failure, and close behavior.

## Local performance evidence

The direct pre/post query comparison uses the same machine and the baseline recorded
in [the Phase 6 baseline](PHASE_6_BASELINE.md):

| Scenario | Before | Trie | Change | Before allocation | Trie allocation |
|---|---:|---:|---:|---:|---:|
| exact | 44.557 ms/op | 5.654 ms/op | -87.31% | 10,505,505 B/op | 10,577,141 B/op |
| high expansion | 4.598 ms/op | 2.412 ms/op | -47.54% | 5,166,914 B/op | 5,343,536 B/op |
| no match | 34.447 ms/op | approximately 0.001 ms/op | over -99.9% | 2,763 B/op | 1,792 B/op |

All eight final 100,000-term benchmark scenarios pass a setup-time full-scan OSA
oracle. The other final means are 0.061 ms/op substitution, 0.073 insertion, 0.056
deletion, 0.059 transposition, and 0.003 two-edits. Those sharply pruned cells allocate
approximately 4.9 to 52.6 KB/op. Exact and high-expansion allocation remains dominated
by accepted expansions, candidate bitmap construction, and scoring preparation.

The required build/publication tradeoff is explicit:

| Workload | Before | Trie | Before allocation | Trie allocation | Allocation change |
|---|---:|---:|---:|---:|---:|
| raw 10k build | 217.068 ms/op | 239.780 ms/op | 258,498,192 B/op | 270,895,258 B/op | +4.80% |
| one replacement | 1.764 us/op | 2.591 us/op | 6,896 B/op | 9,608 B/op | +39.33% |
| 100 replacements | 432.644 us/op | 424.949 us/op | 666,529 B/op | 786,885 B/op | +18.06% |

The publication percentages include the cost of adding and removing immutable trie
paths; the one-replacement absolute change is 0.827 us and about 2.7 KB. Short build
and publication confidence intervals are too wide for latency claims. Phase 7 must
review this cost in the 1M mixed-reader/writer lane, including writer throughput and
queue depth, before V3.1 release evidence is accepted.

## Compatibility and repository gates

- [x] Focused trie, expansion, fuzzy, search, Explain, and lifecycle suites: pass.
- [x] Complete core suite: 280 tests, zero failures/errors/skips.
- [x] Processor reactor: 5 tests, zero failures/errors/skips; travel example builds.
- [x] Independent V1-, V2-, and V3-style consumer compilation and execution: pass.
- [x] Published V1/V2/V2.1/V3.0 Japicmp comparisons: pass in an isolated Maven
  repository.
- [x] The only Phase 6 bytecode-public addition is the contract-authorized,
  Javadoc-hidden `FuzzyVocabularyAccess.forEachWithinEditDistance` bridge; no
  supported API is added.
- [x] Strict release sources, Javadocs, and artifact packaging: pass.
- [x] Existing JMH identities remain unchanged; package build, full fuzzy matrix
  guards, and repository smoke fork pass.
- [x] `git diff --check`: pass.

Phase 7 may now add the protected `ranked-v31` feature lane and execute the 1M mixed
concurrency and two-lane evidence plan. Any writer-side concern found there is handled
as a measured publication optimization, not by weakening trie/posting atomicity.
