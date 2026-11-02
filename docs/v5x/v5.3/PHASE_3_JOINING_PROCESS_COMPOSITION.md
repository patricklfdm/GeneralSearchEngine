# Joining process physical and transport composition

`scripts.v53.joining_process_composition` now replays one original joining
process history from bootstrap through placement, interrupted initialization,
native FINAL, the new-view BARRIER and stable cold reopen. The result remains
`PARTIAL`: complete export/control authority, continuous retention-ledger
composition, the final-source process catalogue and Phase 3 are still **OPEN**.

This extends the [initialization transaction reader](PHASE_3_JOINING_INITIALIZATION_PROCESS.md).
No production Java, wire/storage format, fixture workload, time/resource limit,
workflow or Required job changes in this batch.

## One original history

The ordinary joining fixture starts initialization before old-majority
preparation and performs it inside the parent JVM. The process fixture starts
after that preparation, kills a fresh joining child, then reopens the same
original roots in a second child. Its parent subsequently reopens the completed
owner before performing the unchanged retained grant and continuation steps.
Treating those histories as interchangeable would miss actual process
boundaries and require nonexistent early-start observations.

The new reader first verifies the retained process collection and exact
initialization transaction. It then projects actual parent and child EVENT
records in the shared trace's original order into a temporary copy. Child WIRE
records supply their original encoded responses; sends, receiver reads and
response deliveries bind them to their actual positions. A position map retains
each event's origin and original trace index. No missing event, force, request
or authority is synthesized. The original files and recorded absolute paths
remain unchanged; paths identify originals and are never opened on the reader's
machine.

| Layer | Required evidence |
| --- | --- |
| Child lifetimes | Distinct original PIDs, exact halt/SIGKILL exits, locks, stdout/trace equality and drain observations from the collection reader; no overlapping children or events outside a child lifetime |
| Initialization | Independently derived seed/ledgers, original candidate prefixes and inode identities, exact recovery callbacks, refused native use while a decision is incomplete, READY after completion |
| Physical history | Existing bootstrap/catalog/publication/placement/retirement derivation, whole pre-initialization custody, unchanged old-majority preparation at all four process snapshots, every captured grant, FINAL/BARRIER and cold owner inventories |
| Request specification | Plan, root manifest, identity, target membership, proposer and original paths derived from the physical history, rather than trusted as producer input |
| Transport | Every original send/read/response/delivery and failure attempt; complete transfer bytes, offsets and commit ordering |
| Durable ACKs | Original forced grants, selected installations, accept/proof/publication phases, and complete ownership of every CURRENT callback across parent/child opens |

The ordinary initialization reader retains its exact early-copy and original
single-process force-order checks. Only its reusable native reopen-order checks
and initial-current comparison have been separated into methods; the dedicated
process subclass supplies checks for the different original lifecycle.

## Development verification

The [receipt](phase3-evidence/joining-process-composition.json) pins the original
producer and current reader files and records the actual validation results.
The retained successful `3-ADD / SEED_PREFIX_WRITTEN / halt` development history
is the same original used by the previous transaction reader. This batch does
not rerun the native workload. That producer predates the final read-only
discovery-scan correction and this reader; replay cannot turn it into a
final-source cohort member.

The original composition includes 19 captured grant comparisons, 28 continuation
owner snapshot comparisons, 11 slots, 2,216 wire exchanges and 689 committed
transfers. All 265 CURRENT callbacks are assigned to 69 actual lifecycle
bindings. Exact grant/selection/slot force checks precede any accepted ACK.

Eleven original-first mutations cover foreign child owners, overlapping
processes, early parent reopen, missing child force, premature READY,
unexplained original files, altered old preparation, substituted process input,
missing child wire response and corrupted cold-reopen bytes/force order.
Each disposable copy must fail for its declared reason; an unrelated original
failure is never a passing negative. Parent/child copies are changed
consistently where needed so rejection tests semantic order, not just copied
trace equality. The unchanged packed/unpacked original must produce the same
result at another path.

For an existing original capture:

```bash
python3 -B -u -m scripts.v53.joining_process_composition /path/to/original/raw \
  --case 3-ADD,JOINING_RETENTION_SEED_PREFIX_WRITTEN,halt --qualify
```

The finite callback tests cover the declared 360 combinations conditionally.
They are not 360 native executions. Full process admission still needs the
remaining export/control/continuous-ledger composition and whole-case
final-source execution with downloaded replay. These long executions remain
deferred to the planned hosted parallel acceptance; a death/recovery/continuation
history must stay indivisible.
