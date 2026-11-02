# Phase 3 — ordinary REMOVE ballot continuity

The ordinary four- and five-voter REMOVE path now composes its existing
[captured retirement prefixes](PHASE_3_REMOVE_PREFIXES.md) with the allocator and
promise rules shared by the [REMOVE process reader](PHASE_3_REMOVE_PROCESS_BALLOT.md).
This fills a reader gap before final-source seven-profile qualification. It does
not substitute ordinary execution for interrupted-process evidence.

## One derived history

The only seed is the independently replayed admitted prelude through RESERVE,
PREPARE, READY and SEAL. Original bootstrap bytes, calls, selected sources,
entries, images and generations determine that state. A first development probe
incorrectly started from bootstrap alone and failed the original before-network
allocator comparison. That failed probe is retained. The correction derives the
prelude rather than accepting an observed snapshot as the counter seed.

Each of the three subsequent old/joint/new campaigns must bind its original
selected voter set, local reservation, complete promise write/force transaction,
grant return and installation. A remote grant cannot allocate a local counter;
every local grant must use exactly one earlier reservation and its original
storage identity. Extra reservations, reused forces and unbound promise callbacks
fail. Applied, published, installed and final closed states compare the derived
allocator and highest durable promise without resetting either one.

The shared algorithm has separate hooks for the ordinary three activations and
the process history's interrupted activation plus resumed activations. Process
snapshot/reopen handling and its existing rejection reasons remain unchanged.
Ordinary snapshots use their actual voter and original apply/publication boundary;
an inactive old voter does not acquire a fabricated snapshot or vote.

## Original-first evidence and negatives

```bash
python3 -B -m scripts.v53.remove_ballot_evidence ORIGINAL_RAW ORIGINAL_CAPTURES \
  --profile 5-REMOVE --qualify --workers 2
```

The original physical, network, temporal export, continuous peer/future retention,
retirement and captured-prefix chain must pass before ballot replay or any
negative worker starts. The capture sidecar is mandatory and remains bound to
the same original event/result bytes. Callback-only historical qualification
cannot replace those transient file observations.

Eighteen allocator/promise mutations run on disposable copies. Physical files,
wire bytes, directories and all non-ballot observations must be unchanged.
Continuous retention/retirement is replayed on each changed copy; the ballot
reader must then reject it for its exact designated reason. The copied trace
cannot use the original capture-index/hash sidecar as though it were newly
captured, so the mutated full prerequisite/prefix chain is explicitly not claimed.
Original sidecars and histories are rechecked before completion. Missing targets,
unrelated errors, accepted mutations and any failed worker block qualification.

Concurrency is bounded to one through four independent replay workers. Native
execution, measurement retries and workflow dispatch are outside this reader.
The [receipt](phase3-evidence/remove-ballots.json) records the actual tests,
original producer/reader identities, negative results, process compatibility and
archive/extracted replay. Historical evidence remains distinct from the final
source cohort.

Measured validation: all 1,908 V5.3 Python tests pass, including fifteen new
conditional regressions. Both retained ordinary profiles pass the complete
captured-prefix prerequisite and all eighteen exact ballot negatives each.
The four-voter history binds 3 reservations, 8 promises and
32 allocator/promise comparisons each; the five-voter history binds
3, 9 and 37 respectively. Their 761 and
876 captured retirement prefixes retain their original authority.

The unchanged retained SIGKILL history returns exactly the preceding complete
process result. Its earlier eighteen negatives were not rerun in this batch;
the ten existing process-ballot tests remain in the full passing suite.
All three original histories also replay identically after archive extraction
with assertions disabled. The 26,972,414-byte archive contains 20,972
files: original histories and sidecars, producer manifests, the complete qualified
reader and diagnostics. Original and extracted inventories remain unchanged.

## Remaining closure and rollback

All-seven-profile qualification on one final source, complete process/fault
cohorts, combined bounds and frozen S/N coverage remain OPEN. This entry does not
claim complete original-observation coverage, public readiness or Phase 3 closure.
The long cohorts remain in the [deferred acceptance plan](PHASE_3_DEFERRED_ACCEPTANCE.md).

Rollback removes the ordinary adapter and restores the shared process reader's
inline initialization/boundary calls. Keep original raw histories, capture
sidecars, failed probes and frozen reader manifests. No Java, POM, workflow,
persisted format or resource/time limit changes belong to this batch.
