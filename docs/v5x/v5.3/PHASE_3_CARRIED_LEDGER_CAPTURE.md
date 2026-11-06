# Phase 3 — carried peer and future ledger file capture

Phase 3 remains **OPEN**. This batch extends the
[application/publication capture](PHASE_3_CARRIED_COMPLETION_CAPTURE.md) with
peer-retention and future-retention file prefixes and cold reseals. The native
collector and independent projection are implemented; their complete two-process
composition has not yet been executed or admitted.

## Continuous authority and exact files

The [ledger model](../../../scripts/v53/native_ledger_files.py) reuses the existing
[continuous retention reducer](../../../scripts/v53/native_carried_transition_retention.py).
That reducer derives maintenance, selected-source merging, publication promotion,
future recording and clearing from original history. Intermediate snapshots and
reported revision numbers do not reset the ledger chain.

Each original write is bound to the same owner's independently modeled operation:

| Ledger operation | Preceding file-state boundary |
| --- | --- |
| Peer maintenance and observations | `FLOOR_BEFORE_RETURN` |
| Peer selected-source merge | `INSTALL_PARENT_FORCED` |
| Peer publication promotion | `PUBLICATION_RETIRED` |
| Future recording | `APPLY_BEFORE_RETURN` |
| Future clearing | `PUBLICATION_RETIRED`, with the preceding peer promotion applied |

The model compares all existing file-prefix anchors with the continuously derived
ledger state. It then derives complete replica inventories at the seven write
callbacks: before write, exact half prefix, complete write, file force, candidate
parent force, rename and active parent force. The old active remains selected
until rename. Unrelated files and directories must remain exact. A preceding
unrelated operation, stale anchor, missing callback, overlapping write or wrong
predecessor cannot supply a usable context.

Each original reopen has peer and future active-file/parent reseals. These retain
the already derived revision across group death and match the original cold
inventory; reopening cannot start a new ledger history. The two declared process
cuts interrupt ACCEPT/PROOF, so this batch does not claim partial ledger-write
crash recovery. Future ACK/promotion/clear notifications and learner ledgers are
not relabelled as these physical write callbacks.

## Collection and independent replay

The sixth optional recorder uses the original resource observer's root, PID,
lifetime, event index, owner and terminal digest. It preserves the existing
2048-capture, 512-file, 64-MiB-file and 256-MiB-child limits. Incomplete ledger
transactions cannot claim CLOSED or borrow the vote-rename CUT_PREFIX exception.

The [native reader](../../../scripts/v53/native_carried_ledger_prefixes.py) requires
the complete completion/vote/campaign/FLOOR/retirement/resource/history chain.
`previous/` contains that entire completion wrapper; `ledgers/life-1` and
`ledgers/life-2` contain new sidecars. Full originals must pass before mutation
credit. The reader defines 28 negatives, including identity/inventory errors,
premature replacement, full content at a half-prefix point, leftover candidates,
changed active/resealed revisions and changes outside the ledger. Every rejection
must have its declared reason; original evidence remains unchanged.

## Development evidence

The [development index](phase3-evidence/carried-ledger-prefix-development.json)
records these scopes separately:

- Twenty-four focused Java tests pass. The new short fixture performs two real
  future recordings, one peer promotion, one future clear and three owner opens.
  All six peer/future reseal pairs and four writes produce 40 captured inventories;
  the writer-lock probe and zero resources after close pass. Shared observation
  identity is checked across all six optional recorders.
- The [component reader](../../../scripts/v53/ledger_prefix_component.py) checks
  all 40 inventories and 12 exact physical negatives, including reseal damage.
  It uses conditional original transaction snapshots; it does not establish
  native protocol authority or crash recovery. It replays identically after
  relocation with Python assertions disabled.
- Related Python tests pass 259 cases; 66 boundary tests also pass with assertions
  disabled. They include stale-anchor, wrong operation, wrong predecessor,
  rollback on reopen, missing force, duplicate anchor and original-first guards.
- The unchanged FINAL and INTENT native originals yield 298 and 487 **expected**
  ledger prefixes: 103 writes and 64 reseal callbacks across the two histories.
  Their 6711 non-ledger file-prefix anchors match the continuous revisions. The
  peer/future retention receipts are identical to the prior retained qualification.
  No new native capture or process death is credited by this projection.

For the later composed acceptance run:

```bash
mvn -o -B -ntp -f reactor/pom.xml -pl :general-search-engine-replication -am \
  -Dtest=V53NativeCarriedLedgerPrefixProcessTest \
  -Dsurefire.failIfNoSpecifiedTests=false test

python3 -B -m scripts.v53.native_carried_ledger_prefixes \
  general-search-engine-replication/target/v53-native-carried-ledger-prefixes/run-<id> \
  --qualify
```

Remaining: actual composed native vote/completion/ledger qualification, core
scratch files, complete simultaneous resource maxima, the other carried-process
axes, application-ACK recovery and final-source hosted admission. Production
Java, POM, workflows, runtime limits, frozen workload and hosted catalogue are
unchanged; no paid-cloud or hosted experiment is run here.
