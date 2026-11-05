# Phase 3 required-four direct export composition

This extends [stable direct ownership](PHASE_3_DIRECT_EXPORT_OWNERSHIP.md) across
the complete required-four replacement history, alongside
[joining metadata extents](PHASE_3_JOINING_METADATA_EXTENTS.md). The
[development index](phase3-evidence/required-four-direct-exports.json) retains
the checks. Phase 3 remains OPEN.

## Derive calls from admitted originals

The original SELECTED records determine each activation proposer and selected
receiver. Each expected local borrow binds its exact BASIS and PROMISE bytes,
grant return and installation interval. Repeated rounds sharing one SELECTED do
not invent additional activation calls. Every observed selection force and
installation must be accounted for.

The grant capture reader already pairs `GRANT_BEFORE_RETURN` with the later
`GRANT_CAPTURED` observation. The source-window model now preserves that original
`returnEvent` association. The direct reader checks its node, capture BASIS and
ordering; it does not search after the capture for a replacement grant event.

Admitted floor inputs determine maintenance intervals and generation bindings.
Network maintenance owns a local 4096-byte prefix borrow. Direct fixture floors
already receive their physical copies from the fixture and do not execute that
borrow path. They therefore do not gain invented runtime ownership markers.

One generation can legitimately be borrowed again later. The common reader now
matches each observed allocation to a unique original operation interval, while
retaining exact content/extent and release checks. It rejects duplicate or
ambiguous expectations, missing calls and attempts to reuse one successful call
for another interval. Invalid expectation nodes, types and out-of-trace points
are rejected before matching.

## Composition entry

The existing resource entry now accepts direct-export checking for required-four:

```bash
python3 -m scripts.v53.native_resource_evidence "$RAW" \
  --profile 5-REPLACE-required-four \
  --source-control --control-closes --export-ownership \
  --joining-requests --joining-extents --direct-exports
```

The same original physical, publication, network, content, maintenance and source
accounting prerequisites still run first. Direct ownership checks run on the same
resource/cleanup observations and original maintenance reader. Unattached export
allocations remain a failure; other resource scopes cannot be silently omitted.

The twelve existing exact direct-ownership negatives are available for that
profile through:

```bash
python3 -m scripts.v53.direct_export_negatives "$RAW" \
  --profile 5-REPLACE-required-four
```

The negative entry independently admits the unmodified complete original before
mutating resource observations. It does not replace the separate joining extent,
probe, rollback or physical-peak obligations.

## Retained validation

- Thirteen new reader tests and adjacent suites total 259 passing Python tests.
  Three repeated-content regressions fail against the original reader and pass
  after correction, for activation, SELECTED and maintenance respectively.
- The historical required-four original passes complete physical/network/content/
  maintenance replay. The new derivation finds 72 intervals: six activation,
  thirteen SELECTED and 53 network maintenance. Three content keys each occur in
  two distinct intervals. Replay and derivation took 170.822 seconds locally.
- The stable original still passes full resource/direct replay and all twelve
  exact direct negatives. It retains its original historical-source scope.

The first derivation failed because it searched for grant return after capture;
that diagnostic and the original precondition report remain retained. Early
synthetic fixture failures also remain: the added interval spacer initially used
the wrong charge field/type and reused an allocation UUID. Corrected fixtures
preserve the original charge schema and distinct allocation identity. None of
these failures is counted as positive qualification.

Artifacts and reader hashes are under
`target/v53-required-four-direct-exports/`. Production Java, resource limits,
deadlines, formats and workflows are unchanged. No new Java execution or long
native history was run in this batch.

The historical required-four source predates current export ownership bindings.
Deriving its expectations does not qualify current allocation/cleanup markers.
Current-source whole joining resource composition, independent probe/rollback
content, physical custody and simultaneous maxima/headroom, final cohort
admission and hosted execution remain open. The phase plan remains twelve review
requirements and 544 planned hosted histories; the 3310 S cases belong to Phase 5.
