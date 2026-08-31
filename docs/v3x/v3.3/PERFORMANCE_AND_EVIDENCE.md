# V3.3 performance and evidence contract

## Evidence anchors

Published `v3.2.0` is the source, behavior, and compatibility anchor. Existing cloud
families remain immutable:

- `v3.0.0-cloud` remains the unchanged TEXT/BOOL/PHRASE/FUZZY regression family; and
- `v3.1.0-ranked-cloud` remains the separate phrase-slop/BOOL-minimum feature family.

Pagination or total-hit metrics are not inserted into either frozen preset. Phase 1
captures a same-machine pre-change baseline from exact signed `v3.2.0` and the current
benchmark harness before production implementation.

Phase 0 creates no paid cloud run, preset, workflow, or baseline family.

## Required local benchmark surfaces

### First-page regression

Compare ordinary `search(SearchRequest)` with first-page disabled-total execution over:

- 100k and 1M corpora;
- TEXT, exact/sloppy PHRASE, FUZZY, nested BOOL, BOOST, and filters;
- limits `1`, `10`, and `100`;
- sparse, medium, and dense match rates; and
- distinct-score and equal-score-heavy corpora.

Report latency, allocation, GC, hit/score checksum, evaluated candidates, and retained
page cardinality. Correctness requires bit-for-bit hit parity. Disabled pagination
overhead is reported as a workload-specific delta, not a universal promise.

### Cursor continuation

Measure page sizes `1`, `10`, and `100` at page depths `1`, `10`, `100`, and `1,000`
when corpus cardinality permits. Separate:

- query normalization/planning;
- candidate and filter evaluation;
- scoring before/after anchor;
- bounded page retention;
- cursor construction/validation; and
- equal-score tie-heavy comparison.

The initial implementation may still score all candidates on every page. V3.3 does
not claim O(page size) continuation or deep-page speedup without evidence and a
semantics-preserving physical design.

### Exact total hits

For the same matrix compare `DISABLED` and `EXACT`. Record evaluated candidates,
matching count, latency, allocation, and GC. The expected implementation increments a
primitive counter during existing evaluation; evidence must prove there is no second
query/filter/analyzer pass.

Exact mode is not required to be free. Disabled mode must not allocate a count value or
change hits. No lower-bound or early-termination performance claim is allowed.

### Cursor validation and retention

Measure valid, stale, different-engine, different-request, and unsupported rejection
paths outside the primary success matrix. Cursor construction must be constant-sized
with respect to corpus and query result cardinality.

Retained-heap inspection covers one, 1,000, and 100,000 live cursors plus full release.
It verifies absence of retained snapshot/index/document graphs and absence of an
engine-side cursor registry.

### Concurrency and lifecycle

Mixed evidence includes ordinary readers, first/deep page readers, exact-count readers,
highlighted readers, Explain, and one bounded writer. Record reader latency/throughput,
successful/stale page counts, writer progress, queue depth, publication rate,
allocation/GC, errors, and final oracle agreement.

Dynamic index create/drop and close are exercised as correctness workloads rather than
folded into steady-state latency averages.

## Profiling and optimization policy

Each implementation stage follows:

```text
exact-v3.2 baseline
-> one narrow implementation step
-> focused correctness / six-baseline compatibility
-> allocation and execution profile
-> focused page/count rerun
-> ordinary and highlighted regression suites
```

Profiles distinguish normalization, planning, candidate iteration, filter execution,
scoring, anchor comparison, page heap retention, exact counting, cursor creation,
result construction, and GC.

Optimization may skip retaining candidates before the anchor only when it still
evaluates every required match/score fact and preserves exact totals. It cannot change
score arithmetic, tie order, cursor validation, stale behavior, failures, snapshot
isolation, or Explain.

No global mutable cache, cursor registry, stale-snapshot registry, unbounded thread
local, or physical plan reuse is allowed as a performance shortcut.

## Timeout/cancellation decision evidence

After pagination works, profile high-frequency phrase, large fuzzy vocabulary, dense
BOOL, expensive filter, deep page, and exact-count cases. Identify which latency is in
engine-controlled cooperative loops versus arbitrary consumer callbacks.

If a cancellation design is proposed, measure disabled-control overhead and bounded
check frequencies before amending the contract. If evidence does not justify a safe
surface, record deferral; do not add speculative public methods.

## Cloud boundary

A future canonical page lane requires a separately reviewed preset/mode with bounded
cost, immutable identity, Standard provisioning, retention, cleanup, and Cloud
Benchmark V2 evidence lifecycle. It establishes a new family and cannot replace or be
directly aggregated with `v3.0.0-cloud` or `v3.1.0-ranked-cloud`.

Local evidence is sufficient for Phase 0 and initial implementation unless a later
contract identifies a release-critical scale claim requiring paid cloud execution.

## Acceptance policy

Correctness, six-baseline compatibility, first-page parity, exact counts, cursor
opacity/retention, stale behavior, writer progress, and evidence validity are hard
gates.

Phase 0 freezes no fixed latency or allocation percentage because no comparable
pagination history exists. Material ordinary-path or first-page regressions require
profiling and review; unrelated benchmark cells cannot be averaged to conceal them.
A numerical CI threshold needs repeated comparable histories and a separate accepted
contract.
