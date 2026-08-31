# V3.2 Phase 3 checklist

Status: TEXT highlighting implementation and local evidence are complete on an
independent branch; protected PR/master acceptance remains pending. PHRASE, FUZZY,
BOOL, and BOOST evidence remain explicitly deferred to Phase 4.

## Accepted entry boundary

- [x] Phase 2 merged to protected `master` as source commit `0729d77`.
- [x] The independent `feat/v3.2-phase3-text-highlighting` branch starts from that
  accepted merge.
- [x] Active coordinates remain `3.2.0-SNAPSHOT`; all five published compatibility
  baselines remain mandatory.
- [x] Phase 3 adds no stored offset payload, sidecar, HTML renderer, formatter
  callback, analyzer composition, cloud preset, or release-family mutation.

## Public API and compatibility

- [x] The exact frozen final request/result family is public under the search package:
  `HighlightedSearchRequest`, `HighlightedSearchResult`, `HighlightedSearchHit`,
  `FieldHighlight`, `HighlightFragment`, and `HighlightSpan`.
- [x] Builders validate nulls, duplicate field names, context, fragment cap, and the
  required field set; built requests and all result lists are immutable snapshots.
- [x] Public result constructors enforce context-free range, ordering, containment,
  uniqueness, and substring-length invariants.
- [x] `SearchEngine.search(HighlightedSearchRequest)` is an additive default method
  whose third-party fallback rejects null first and then throws
  `UnsupportedOperationException`.
- [x] The frozen public descriptor fixture and V3 consumer compile and execute using
  only supported public API.

## Integrated TEXT highlighting

- [x] The built-in engine captures exactly one immutable snapshot and prepares one
  canonical plan for the complete highlighted invocation.
- [x] Returned `SearchHit` instances are the exact canonical executor output; score
  bits, order, cardinality, filters, and top-K remain unchanged.
- [x] Only explicitly requested fields of final hits are extracted and re-analyzed;
  every nonempty requested source is offset-sequence validated.
- [x] Pure TEXT leaves select every matching normalized source occurrence and query
  duplicates cannot create duplicate visible spans.
- [x] Range normalization sorts, deduplicates, merges overlaps, preserves adjacency,
  and fragment construction obeys context, surrogate safety, overlap coalescing,
  earliest-window order, and per-field caps.
- [x] Null/empty sources and fields without a matching range are omitted without
  removing their canonical hit.
- [x] Non-TEXT ranked trees fail explicitly in Phase 3; no partial PHRASE, FUZZY,
  BOOL, or BOOST evidence is presented before Phase 4.

## Validation, lifecycle, and diagnostics

- [x] Failure order covers null request, closed engine, canonical fields,
  `OffsetAnalyzer` capability, wrapped request/index validation, canonical execution,
  extraction, analysis, and complete offset validation.
- [x] Legacy analyzers, noncanonical fields, missing indexes, malformed offset output,
  extractor/analyzer exceptions, closed engines, and the Phase 3 query-family boundary
  have focused fixtures.
- [x] Dynamic text-index creation/drop and a blocked analyzer plus concurrent update
  prove index lifecycle behavior and absence of snapshot mixing.
- [x] A fixed-seed 300-trial integrated differential suite compares canonical hits,
  structured filters, duplicate TEXT terms, spans, windows, and caps with independent
  references.
- [x] A separate fixed-seed 2,000-trial fragment suite covers overlapping, duplicate,
  adjacent, capped, and surrogate-boundary ranges.

## Evidence and required gates

- [x] `V32TextHighlightBenchmark` contrasts ordinary TEXT with explicit top-K TEXT
  highlighting and consumes hit, field, fragment, and span checksums.
- [x] The bounded JMH smoke gate discovers and executes the new highlighted surface.
- [x] The Phase 3 local baseline records environment, protocol, values, allocation,
  limitations, and the unchanged cloud boundary.
- [x] The full core, reactor, strict Javadocs, five-baseline artifact compatibility,
  consumer, fresh-isolated resolution, version, JMH smoke, and diff-hygiene gates pass.
- [x] No paid cloud run is required because Phase 3 adds a local opt-in API without
  changing either immutable cloud family or protected workflow.

## Phase 4 handoff

- [x] Phase 4 may add deterministic PHRASE witnesses, scoring-selected FUZZY evidence,
  and recursive BOOL/BOOST evidence composition without changing this public family.
- [x] Phase 4 must preserve the Phase 3 canonical-hit oracle, one-snapshot boundary,
  validation order, fragment algorithm, and explicit top-K source re-analysis model.
- [x] Stored offsets, HTML, analyzer composition, and cloud-family changes remain
  outside that handoff.

Phase 3 is complete only after all required gates pass and this branch merges through a
protected PR. Phase 4 must start from that accepted merge commit on a new independent
branch.
