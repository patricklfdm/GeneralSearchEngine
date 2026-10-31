# Original-copy observation replay

Phase 3 remains **OPEN**. This batch repairs independent Python reconstruction
for the retention semantics already implemented in `bafce01e`. It replays retained
native histories from the [recovery-heartbeat batch](PHASE_3_RECOVERY_HEARTBEAT.md);
it changes no Java runtime, POM, workflow, timing or capacity limit and runs no new
workload. The earlier failed reader result remains retained.

## Exact reconstruction

The new explicit `--confirmed-retention` mode reconstructs genesis observations
as byte-identical no-ops. Later complete original copies create exact confirmation
bytes, preserve earlier checkpoint-renewal obligations and retain unconfirmed
future endpoints. Revision and previous-digest fields are derived, never ignored.
An equivalent later manifest cannot replace the already retained original proof.

The enclosing reader first derives each generation from bootstrap, original
grants, votes and publication. The observation helper accepts those complete
inventories and checks the exact current endpoint, root, view and permanent
identity. Metadata consistency alone does not establish historical authority.
Original transfer delivery must precede the governing floor; the reader then
requires exactly the derived number of complete retention force sequences.
Genesis cannot invent a write, and missing, additional or reordered force events
cannot pass merely because the final bytes match.

The carried-entry history exposed a second old-model gap: after completing its
carried slot, native maintenance retires the first campaign's obsolete empty-tail
source. Its reader now derives that particular source from the original two
campaigns, checks the exact published range covering it, retains the current
source, and derives the compacted journal from original frames. All other files
remain byte-for-byte exact. The complete source-retirement/rotation sequence must
occur after generation retirement and before floor release. This narrow projection
does not authorize arbitrary source deletion or qualify interrupted retirement.

The default mode retains the historical reconstruction. There is no automatic
mode detection, retry with weaker rules or fallback after an original failure.
The mode is selected alongside the producer's frozen input manifest. Selected
source merging with arbitrary confirmation histories remains a separate open task.

## Retained-history validation

The [source-bound receipt](phase3-evidence/observation-replay.json) records the
original inputs, reader hashes, results, failed attempts and verified archive.
Each negative qualification validates the unchanged original first and requires
the precise rejection reason for every mutation.

| Retained history | Reader | Negative executions |
| --- | --- | ---: |
| Current stable round | Round lifecycle | 18 |
| Current discovered stable round | Round lifecycle | 18 |
| Current READY-only heartbeat | Heartbeat | 23 |
| Current carried-applied round | Round lifecycle | 25 |
| Historical READY-only heartbeat | Legacy heartbeat | 13 |
| Current stable projection | Native physical/network | 37 |
| Current discovered projection | Native physical/network | 41 |
| Current carried projection | Carried physical/network | 26 |

All eight qualifications pass. These are **five histories**, with three additional
reader projections, not eight independent executions or 201 distinct fault
families. The projections remove only the enclosing `round-result.json`; original
physical and network material is unchanged. All five wrong-mode checks reject the
unchanged original at `applied-1/node-1`; no negatives run on those invalid originals.

The complete V5.3 Python suite passes all **932 tests** in 85.866 seconds. All 318
production/POM inputs match the current producer snapshot. Archive inventory and
hash checks pass, and all five histories reproduce their results after unpacking
to a different directory. The documentation contract and local links also pass.

The new mutations cover forged or missing confirmation bytes, forgotten renewals,
stale endpoints, revision-chain corruption, invented genesis writes, missing or
reordered observation forces, retained/deleted wrong sources, changed journal
bytes, and premature or incomplete source retirement. Eight focused new unit tests
also check projection boundaries and original-first behavior; those conditional
unit fixtures are not native durability evidence.

To replay a matching current raw history, use one of:

```bash
python3 -B -m scripts.v53.round_driver_evidence "$RAW" --confirmed-retention --qualify
python3 -B -m scripts.v53.round_driver_evidence "$RAW" --confirmed-retention --discovery --qualify
python3 -B -m scripts.v53.heartbeat_round_evidence "$RAW" --confirmed-retention --qualify
```

For historical legacy evidence omit `--confirmed-retention`. The retained
`cases.json` binds each input to its mode; it is not a substitute for original
validation. The archive contains the original five histories, source snapshots,
producer input hashes, analysis tools and both unsuccessful and corrected results.

## Remaining work and rollback

This closes the component reader mismatch identified by the recovery-heartbeat
receipt. It does not turn that batch's successful three-owner producer into
complete independent competition acceptance. Whole automatic-history replay,
native joining/joint continuation, cold process recovery, every frozen profile
and the other Phase 3 closure rows remain open.

Rollback removes the explicit new reader mode and its helpers together. Persisted
state and runtime behavior are unaffected. Preserve both the old failed result and
the repaired source-bound result; do not replace a failed original with a retry.
