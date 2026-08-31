# V3.2 Phase 0 checklist

Status: contract accepted on protected `master` as `9f48259`. Its frozen decisions
remain the authority for the completed implementation phases and Phase 6 hardening.

## Entry boundary

- [x] V3.1 Phase 8 and post-publication evidence are complete on protected `master`.
- [x] Signed `v3.1.0`, both Central artifacts, remote verification, and the GitHub
  Release are immutable and accepted.
- [x] The V3.2 entry commit is
  `70bfd7890e2bcf8aa555f8dfd8c18a57d48ba3da`; exact-commit `CI / Required` passes in
  [run 33337438109](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/33337438109).
- [x] Published `1.0.0`, `2.0.0`, `2.1.0`, pinned `3.0.0`, and pinned `3.1.0` remain
  mandatory compatibility baselines.
- [x] Project identity remains final `3.1.0` throughout Phase 0.
- [x] No V3.2 implementation, version conversion, benchmark preset, workflow, or paid
  cloud run is part of Phase 0.

## Frozen architecture decisions

- [x] V3.2 retains immutable snapshots, structural sharing, lock-free readers, one
  asynchronous writer, and atomic publication.
- [x] Highlighted search uses the canonical V3 query normalization, planner, scoring,
  top-K, and Explain semantics; no second retrieval pipeline is introduced.
- [x] One highlighted-search invocation captures one snapshot and completes hits and
  highlights within that invocation.
- [x] Offsets are not stored in postings, positions, snapshots, the fuzzy trie, or a
  per-document sidecar.
- [x] Only returned top-K documents and explicitly requested fields are offset
  re-analyzed.
- [x] Ordinary index/search/Explain paths do not construct offset result objects.
- [x] Match evidence remains package-private, invocation-local, and bounded.

## Frozen token/offset decisions

- [x] `Analyzer` remains a SAM and `AnalyzedToken` retains its published two record
  components.
- [x] A separate `OffsetAnalyzer` capability and four-component
  `OffsetAnalyzedToken` record are the only required analysis additions.
- [x] Offsets are half-open UTF-16 indices into the exact original Java string.
- [x] Valid ranges are non-empty, within source bounds, and never split a surrogate
  pair.
- [x] Terms may differ from source spelling/length after normalization, but each range
  identifies the minimal contiguous contributing source.
- [x] Later logical-position start/end boundaries cannot move backward; monotonic
  overlap is allowed for multi-token NFKC expansion, and same-position alternatives
  share one exact source range.
- [x] Position gaps and character gaps remain independent; existing term/position
  output must remain identical.
- [x] Built-in SimpleAnalyzer supports offsets while retaining a direct non-offset
  path for ordinary use.
- [x] Legacy analyzers remain fully supported except when their field is explicitly
  requested for highlighting; no approximate offset fallback exists.

## Frozen highlighting surface and semantics

- [x] The additive public family is `HighlightedSearchRequest`,
  `HighlightedSearchResult`, `HighlightedSearchHit`, `FieldHighlight`,
  `HighlightFragment`, and `HighlightSpan`.
- [x] `SearchEngine` receives one additive default `search(HighlightedSearchRequest)`
  capability; third-party implementations remain binary-compatible.
- [x] Request defaults are 40 UTF-16 context units and three fragments per field.
- [x] Results are immutable, preserve canonical hit/requested-field order, and expose
  absolute half-open offsets plus exact fragment substrings.
- [x] TEXT highlights matched term occurrences.
- [x] PHRASE highlights one deterministic least-slop/earliest witness covering the
  complete source range between first and last selected tokens.
- [x] FUZZY highlights occurrences of the same selected expansion used by score and
  Explain.
- [x] BOOL unions every matched MUST and matching SHOULD child; BOOST forwards child
  ranges and structured filters add none.
- [x] Duplicate ranges deduplicate, overlapping ranges merge, and merely adjacent
  ranges remain separate.
- [x] Fragment windows expand without splitting surrogate pairs, coalesce only when
  overlapping, retain earliest windows at the cap, and add no hidden boundary policy.
- [x] The library returns no HTML and owns no markup/escaping policy.
- [x] Highlighting cannot change match, score, order, top-K membership, failure
  precedence, or Explain.

## Explicit deferrals

- [x] Analyzer pipeline/composition requires its own contract after the foundation.
- [x] Single-token same-position synonyms require a separate semantic/scoring/Explain
  contract and are not an implicit Phase 0 authorization.
- [x] Multi-token synonyms, position length, and token graphs are outside V3.2.
- [x] Stemming and ranked prefix are optional independent contracts, not release
  blockers.
- [x] Ranked `mustNot`, advanced fuzzy controls, HTML rendering, stored offsets,
  completion, search-after, total hits, timeout/cancellation, persistence, vectors,
  and distributed retrieval are outside this contract.

## Implementation entry gates — accepted

- [x] Phase 0 PR passes required CI and merges to protected `master` as
  `9f4825976cb0c6e9c3c8862efabd9e648bc315a4`.
- [x] Create an independent Phase 1 branch from the accepted merge commit.
- [x] Convert all active project/consumer coordinates atomically to
  `3.2.0-SNAPSHOT`; published baseline identities remain unchanged.
- [x] Rerun normal clean-home and fresh-isolated five-baseline Japicmp before adding
  public API.
- [x] Capture exact-v3.1 ordinary analyzer/index/search and retained-memory baselines.
- [x] Materialize independent offset, highlight, phrase-witness, fuzzy-selection, and
  fragment oracles before production execution.
- [x] Add reflection/source fixtures for the frozen public descriptors before
  implementation.

## Implementation exit gates — accepted

- [x] Built-in offset analysis passes focused and randomized Unicode equivalence.
- [x] Highlighted hits equal ordinary search hits on one captured snapshot.
- [x] TEXT/PHRASE/FUZZY/BOOL/BOOST ranges pass independent differential oracles.
- [x] Invalid offsets, unsupported analyzers, canonical fields, and failure precedence
  pass focused matrices.
- [x] Mutation, bulk, dynamic-index, snapshot, concurrency, and close lifecycle tests
  pass.
- [x] Ordinary paths prove no offset-result allocation and retain reviewed regression
  behavior.
- [x] Highlight allocation/latency evidence is reviewed across the frozen matrix.
- [x] Five published API baselines, all consumers, strict Javadocs, artifacts, and
  reproducibility pass.

Phase 0 is accepted. Its historical `3.1.0` identity and documentation-only boundary
remain correct even though Phase 1 subsequently changes the active development
coordinate. Any later semantic or public-surface change requires a contract amendment
before production implementation.
