# Phase 3 — continuous REMOVE retention revisions

This batch extends [REMOVE export authority](PHASE_3_REMOVE_EXPORTS.md) using the
same original `4-REMOVE` and `5-REMOVE` executions. Production Java, protocols,
resource limits and workflows are unchanged. No native execution is repeated.
The [receipt](phase3-evidence/remove-retention.json) identifies the original
producer/build, separately frozen reader, source difference, raw inventories,
diagnostics and portable replay.

## Continuous authority

The physical, attempted-network and export/floor readers must pass first. Peer
retention starts from the independently reconstructed public bootstrap, not the
network-stage cut: these histories reach cut 4 while retaining their genesis
revision-zero ledger. The reader compares that derived starting ledger to the
before-network bytes, then carries it through the entire three-campaign history.

Each original acquired floor supplies complete same-cut peer copies. The reader
derives view reconciliation, same-cut observations and conservative renewals in
their actual order. Selected-source merges use the frozen original source
wrappers and exact before-ledger intent; publication promotes only the peers in
the original proof certificate. Unchanged plans consume no write. Each changed
plan must consume exactly one complete seven-callback write/force/rename chain,
with revision increment, immutable root/owner and exact predecessor hash.

The future ledger likewise starts once at revision zero. Each recorded target
uses the original peer lower bound, which can precede the current parent after
deferred renewals. Each record and subsequent clearing increments the continuous
revision and hashes the exact prior bytes. Recording callbacks bind to the same
network exchange: local ACK precedes send; remote ACK follows force and precedes
the offered response. Promotion precedes clearing and publication return.

Installed, applied, published, new grant-source and final closed inventories are
comparisons against derived state. None resets the state. All original opens,
including inactive fourth/fifth voters, must force peer and future active files
and directories in order before accept recovery. These are observed in-process
opens, not a fresh-process crash/recovery qualification.

## Qualification boundaries

| Original | Peer writes (maintenance / selected / publication) | Future writes (record / clear) | Peer / future comparisons | Opens per ledger |
| --- | --- | --- | --- | --- |
| `4-REMOVE` | 40 (27 / 5 / 8) | 22 (14 / 8) | 44 / 36 | 4 |
| `5-REMOVE` | 48 (33 / 6 / 9) | 27 (18 / 9) | 51 / 42 | 5 |

The frozen reader passes all 1582 V5.3 Python tests, including 13 new tests.
The two original qualifications complete in 132.486 and 172.148 seconds.
These are validation times, not new experiment measurements or a runtime SLA.
The sealed archive preserves 20177 files and 2658 directories with exact member
hashes. Both extracted `python -O -B` qualifications reproduce all positive and
negative results exactly, in 122.318 and 160.929 seconds respectively.

Each original has 22 peer and 19 future callback negatives. The full unmodified
physical/network/export authority gate runs before mutation. Negative copies
preserve every original non-event file, wire transcript, empty directory and
non-target event in order; the targeted reader must reject for the exact expected
reason. The mutated full prerequisite is not rerun or counted as the rejection.
An unrelated exception or accepted mutation fails the qualification.

The initial reader-development failure is retained. It had derived the initial
peer plan from network cut 4 instead of the original genesis plan; the corrected
reader derives the admitted bootstrap before comparing that unchanged ledger.
This was a reader assumption error, not a reason to rerun the native histories.

The historical REPLACE future reader keeps its default joining-owner scope and
parent lower bound. Its positive result is compared to the previously retained
result; this compatibility replay does not qualify a new native source/build.

The scope remains **PARTIAL**. Complete generation/source retirement callback
transactions, fresh-process failure histories, the current-source seven-profile
matrix, autonomous election scheduling and frozen acceptance mapping remain
open. Phase 3 is not closed by these two successful component histories.

## Reproduction and rollback

Run the reader on an unmodified collected original:

```bash
python3 -B -m scripts.v53.remove_retention_evidence ORIGINAL \
  --profile 4-REMOVE --qualify --workers 2
```

Use `5-REMOVE` for the other complete history. Workers parallelize only independent
negative copies, never the original continuous experiment. The recorded portable
check uses `python3 -O -B` and requires exact result equality after archive
extraction. Rollback removes this reader, tests and receipt, and restores the
shared future-reader defaults; persisted bytes and production APIs are unaffected.
