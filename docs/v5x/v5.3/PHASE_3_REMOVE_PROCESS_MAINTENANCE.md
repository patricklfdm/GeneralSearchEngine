# Phase 3 — REMOVE maintenance floors across process death

Status: complete-copy acquisition, retained-floor reuse and release are qualified
for the original v2 `4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill` member.
Continuous peer/future revisions, complete retirement callback composition,
the remaining process/profile matrix and Phase 3 remain OPEN.

This extends [temporal exports](PHASE_3_REMOVE_PROCESS_EXPORTS.md). Physical,
attempted-network and export replay must pass first. It uses the same original
native execution and changes no Java, protocol, timing budget or runtime format.

## Authority and lifetime

The reader binds each STATUS hint to the exact original identity, ballot and cut;
a hint alone supplies no deletion authority. Complete original generation members
arrive before the floor reservation. Two local-copy observations enclose network
discovery. Manifest/member/directory force, complete-copy handoff and floor
authority force must follow the exact sequence derived from those members.

The killed proposer leaves a complete durable floor. Its interrupted and cold-open
snapshots must contain exactly the independently derived proposal, authority and
copied members. Recovery finishes the original interrupted retirement under that
floor. The next maintenance reuses those same copies, rechecks the unchanged local
generation and forces the floor again. It cannot invent a new network acquisition
or reset the floor from a later snapshot. Release order and deletion counts are
derived from the actual original copied files.

The history contains 16 network acquisitions, one retained-floor reuse, 47 complete
copy instances (including the three reused copies), 28 remote acquisitions and
16 completed releases. All 1,521 floor observations and 951 retirement-lifetime
observations are accounted for. The first interrupted floor has no release in the
killed process; its original authority survives recovery. Final owner snapshots
must contain no retained floor.

## Qualification

```bash
python3 -B -m scripts.v53.remove_process_maintenance ORIGINAL_V2_PROCESS_ROOT \
  --qualify --workers 4
```

The [receipt](phase3-evidence/remove-process-maintenance.json) binds the full
original producer archive, frozen reader and portable raw inputs. Fifteen negatives
cover missing/duplicate local copies, force/handoff order, recovery resealing,
premature or incomplete release, forged floor scope, discovery/copy ordering and
retirement callbacks outside the governing floor. Every negative preserves all
physical files and passes physical/network/export replay before its exact declared
maintenance rejection. An unrelated earlier failure cannot satisfy a negative.

The original and relocated archive under optimized Python must produce identical
results, with every input hash unchanged. The nine focused guard tests and all
1,662 V5.3 Python tests pass. No native experiment is rerun for this reader.

This is one additional qualification layer for one existing native member, not
another matrix execution. `completeCopyFloorsQualified` and
`retainedFloorRecoveryQualified` are true; continuous retention revisions and
complete retirement callbacks are explicitly false. The lifecycle bounds checked
here do not independently derive every retirement decision or ledger revision.
Rollback removes this reader and its documentation; runtime data is unchanged.

The subsequent [continuous retention reader](PHASE_3_REMOVE_PROCESS_RETENTION.md)
now binds peer/future revisions through these original floors and process opens.
Complete retirement callback composition remains a separate open layer.
