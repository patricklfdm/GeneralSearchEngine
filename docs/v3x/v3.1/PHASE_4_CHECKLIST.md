# V3.1 Phase 4 checklist

Status: complete. No production code or supported API changed in this phase.

## Phrase differential hardening

- [x] Add a deterministic positioned-token differential generator that varies one
  to four query slots, initial and internal gaps, same-position alternatives,
  repeated terms, document positions, empty documents, and slop from zero through
  six.
- [x] Compare 220 generated queries across 30 indexed documents with the independent
  Phase 1 position oracle, including a source-document mutation every seven queries.
- [x] Require candidate safety, match truth, normal-search/Explain equivalence,
  requested-slop diagnostics, and minimum-consumed-slop diagnostics for every
  document.
- [x] Extend dynamic text-index journal replay with exact and sloppy phrase witnesses
  before and after bulk update, removal, drop, and rebuild.
- [x] Prove that a phrase-plus-TEXT BOOL threshold request evaluates the snapshot
  captured before blocked query analysis while a mutation publishes concurrently.

## Ranked mutation and lifecycle hardening

- [x] Compare phrase, filtered BOOL threshold, duplicate SHOULD occurrence, BOOST,
  hit, score, ordering, and Explain behavior with source-document predicates through
  120 deterministic add, update, upsert, remove, remove/add, and bulk operations.
- [x] Verify a failed bulk analysis publishes no partial state, preserves snapshot
  version and document identities without semantic drift, and leaves the writer
  usable for a subsequent successful update.
- [x] Verify missing-index failures after drop, semantic restoration after dynamic
  text-index rebuild, and empty Explain after document removal.
- [x] Retain zero queue-depth, document-count, finite/non-negative score, unique-hit,
  and score-order gates after mutation histories.

## Concurrency and failure precedence

- [x] Repeat the concurrent ranked fixture three times with four lock-free readers,
  300 search/Explain iterations per reader, and 180 single or bulk publications by
  the writer.
- [x] Require every observed hit and Explain result to be valid for its returned
  document, then compare final state with the exact source oracle and require zero
  failed mutations and zero writer queue depth.
- [x] Confirm BOOL shape validation precedes analyzer and snapshot work and that an
  invalid builder remains repairable.
- [x] Confirm logical leaf order determines missing-index versus malformed-analysis
  failure, zero-term leaves skip index resolution, and structured filters do not run
  before ranked planning succeeds.
- [x] Confirm Explain for a missing business ID returns empty before ranked analysis
  or index resolution, while an existing ID follows normal failure precedence.

## Compatibility and repository gates

- [x] Keep production sources, public descriptors, consumer sources, and benchmark
  identities unchanged; Phase 4 makes no new API or performance claim.
- [x] Core suite: 274 tests, zero failures/errors/skips.
- [x] Processor reactor: 5 tests, zero failures/errors/skips; travel example builds.
- [x] Published V1/V2/V2.1/V3.0 Japicmp comparisons: pass in an isolated Maven
  repository; the V3 diff remains exactly the Phase 2 and Phase 3 additions.
- [x] Independent V1/V2/V3 consumer compilation and execution: pass.
- [x] Strict release Javadocs and artifact packaging: pass.
- [x] Existing JMH packaging and repository smoke execution: pass.
- [x] `git diff --check`: pass.

Phase 5 may now profile and optimize phrase allocation and execution under the
frozen semantic, Explain, failure-precedence, snapshot, lifecycle, compatibility,
and evidence-identity contracts proven here.
