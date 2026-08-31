# V3.2 Phase 4 checklist

Status: complete and accepted on protected `master` through PR #54 as merge commit
`1dd81d1`. Lifecycle, concurrency, retained-memory, and optimization decisions remain
the Phase 5 boundary.

## Accepted entry boundary

- [x] Phase 3 merged to protected `master` as source commit `5425299`.
- [x] The independent `feat/v3.2-phase4-query-evidence` branch starts from that
  accepted merge.
- [x] Active coordinates remain `3.2.0-SNAPSHOT`; all five published compatibility
  baselines remain mandatory.
- [x] Phase 4 adds no public API, stored offset payload, sidecar, HTML renderer,
  analyzer composition, cloud preset, or release-family mutation.

## Canonical execution and composition

- [x] Highlighted search still captures one immutable snapshot and prepares one
  canonical scoring plan for the complete invocation.
- [x] The executor exposes invocation-local internal document IDs together with the
  exact canonical `SearchHit`; ordinary search retains its prior result construction
  path and public shape.
- [x] Every highlighted hit remains bit-for-bit equal to the ordinary control in
  score, order, cardinality, filters, and top-K membership.
- [x] Evidence selection walks the already-prepared scoring plan and never parses
  public Explain text or independently replans the query.
- [x] Only matching MUST children and all matching SHOULD children contribute BOOL
  evidence; `minimumShouldMatch` does not hide additional matched SHOULD evidence.
- [x] BOOST transparently forwards its matched child's evidence, including matched
  zero-score descendants.

## PHRASE evidence

- [x] Exact and sloppy phrases use offset-token logical positions, including gaps and
  same-position alternatives, rather than source-string matching.
- [x] One witness is selected by least consumed slop, earliest first-token start,
  then the lexicographically earliest subsequent `(startOffset, endOffset)` tuple.
- [x] The visible phrase range starts at the first witness token and ends at the last;
  intervening original source text remains part of that range.
- [x] Repeated phrase terms, alternative terms, sparse positions, multiple witnesses,
  and deterministic tie-breaking have focused and exhaustive-oracle coverage.
- [x] A matched plan without a valid offset-token witness fails explicitly as an
  analyzer projection contract violation rather than emitting approximate evidence.

## FUZZY evidence

- [x] Evidence uses the exact expansion selected by the canonical per-document fuzzy
  scoring evaluation and highlights every occurrence of that selected term.
- [x] Exact-term priority, weighted-score selection, edit-distance behavior, and
  deterministic lexical ties remain identical to ranked fuzzy semantics.
- [x] No alternate expansion is inferred from source proximity, token order, or
  Highlight-specific scoring.
- [x] Fixed-seed full-scan OSA/BM25 differential trials independently reproduce the
  selected expansion and canonical highlighted hit.

## Normalization and differential evidence

- [x] Evidence from recursive branches is normalized by the frozen Phase 3 sort,
  deduplication, overlap merge, adjacency, fragment, Unicode, and cap rules.
- [x] Requested field order is preserved and cross-field branches contribute only to
  their own requested field.
- [x] Focused fixtures cover least-slop selection, repeated terms, alternatives,
  fuzzy exact/typo/tie cases, nested BOOL/BOOST, zero score, overlap normalization,
  unmatched children, and cross-field evidence.
- [x] Fixed-seed differential suites cover 420 phrase trials, 180 fuzzy trials, and
  220 recursive query-tree trials against independent exhaustive references.
- [x] The complete core suite passes with 337 tests.

## Evidence and required gates

- [x] `V32QueryEvidenceHighlightBenchmark` contrasts ordinary and highlighted search
  for exact phrase, sloppy phrase, fuzzy, and BOOL/BOOST workloads.
- [x] Trial setup rejects any canonical-hit drift and benchmark checksums consume hit,
  score, field, fragment, and span output.
- [x] The bounded JMH smoke gate discovers and executes a Phase 4 query-evidence cell.
- [x] The local baseline records environment, protocol, values, allocation deltas,
  limitations, and the unchanged cloud boundary.
- [x] Core, reactor, strict Javadocs, five-baseline artifact compatibility, consumer,
  fresh-isolated resolution, version, example, JMH smoke, and diff-hygiene gates pass.
- [x] No paid cloud run is required because Phase 4 changes neither immutable cloud
  baseline family, protected workflow, benchmark preset, nor stored index shape.

## Phase 5 handoff

- [x] Phase 5 inherits the exact Phase 4 evidence semantics and canonical-hit oracle;
  it may harden lifecycle, mutation, dynamic-index, and concurrent execution behavior.
- [x] The local allocation deltas are profiling anchors, not frozen thresholds; Phase
  5 may optimize invocation-local analysis and evidence collection without semantic,
  validation-order, or public-API drift.
- [x] Any cloud highlighting lane still requires a separately accepted preset, mode,
  identity, comparison, cost, and retention contract.
- [x] Stored offsets, HTML, analyzer composition, and release-family changes remain
  outside this handoff.

Phase 4 is complete. Phase 5 started from accepted merge commit `1dd81d1` on a new
independent branch.
