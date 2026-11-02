# Phase 3 — REMOVE exports across process death

Status: the retained v2 `4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill`
member has independent temporal export qualification. Continuous maintenance and
retention composition, the full process/profile matrix and Phase 3 remain OPEN.

This extends [the process-network reader](PHASE_3_REMOVE_PROCESS.md) using the same
original bytes. It runs no new native history and changes no Java code, protocol,
budget or runtime format. The earlier physical and attempted-network readers must
pass before this reader can make any export claim.

## Original lifetime boundaries

The interrupted and resumed proposer have two distinct original OPEN/CUT/CLOSED
intervals. Network observations outside either lifetime refuse qualification.
Generation windows start only after the corresponding installation/publication
return and end before the next selector rename. A proposer window is also clipped
at process death; reopening does not bridge the dead interval. Physically derived
snapshots supply the original manifests, packet bytes, images and identity.

Frozen sources start at their exact original grant return. The reader compares
their complete immutable members at every original snapshot. A disappearing source
must have an original retirement transaction in that same interval; absence in a
final snapshot alone cannot invent its retirement time. Every observed grant and
source-retirement boundary must be accounted for. An ambiguous interval is refused.

Journal selection records include the interrupted campaign even though it never
completed a slot. The shared record reader accepts this explicit ordered selection
inventory; its default behavior for earlier healthy histories is unchanged.
INTENT/FINAL payloads are reconstructed from the independently derived installed
catalog, and BARRIER has the empty payload. Their original ENTRY digests must match.
Pending vote, applied-checkpoint and completed-checkpoint windows use the existing
force, promise, view and publication boundaries.

All 167 original transfer sessions and 327 committed transfers are bound across
nine export families: current generation, frozen source, journal, pending record,
pending payload, native vote receipt, applied checkpoint, published local
checkpoint and published record. There are 24 generation windows; no transfer
is accepted solely because its content hash matches a later snapshot.

## Independent qualification

```bash
python3 -B -m scripts.v53.remove_process_exports ORIGINAL_V2_PROCESS_ROOT \
  --qualify --workers 2
```

The [receipt](phase3-evidence/remove-process-exports.json) binds the original
producer archive and the new reader. Eleven mutations cover wrong generation or
source aliases, changed generation/source/receipt bytes, wrong source ballot,
retired source access, premature receipt access, wrong view and forged completed
checkpoint voter. Every mutation must preserve all physical files, pass physical
and network replay, and fail for its declared export reason. Parser errors and
broken transport cannot satisfy this gate. The expiry mutation stays within its
original proposer lifetime; the earlier invalid cross-lifetime attempt is retained
as a development diagnostic, not counted as a successful negative.

Original and relocated archive replays under optimized Python must give identical
results with all input hashes unchanged; both pass all eleven negatives in this
batch. All 1,653 V5.3 Python tests and 26 focused export/guard tests pass. The
prior healthy four- and five-voter
REMOVE export histories are replayed to check the shared reader's default path;
they do not substitute for the restarted history or add process-matrix members.

The result stays `PARTIAL`. Its nested network precondition retains its original
narrower flags; `observedExportAuthorityQualified=true` belongs to this additional
layer. No complete maintenance-floor recovery, continuous retention revisions,
all-cut process qualification, public readiness or Phase 3 closure is claimed.
Rollback removes this reader and its optional selection-inventory argument; no
runtime data migration, cloud execution or workflow change is involved.

The subsequent [maintenance-floor reader](PHASE_3_REMOVE_PROCESS_MAINTENANCE.md)
qualifies acquisition, retained-copy recovery and release in this same history.
It preserves this receipt's narrower flags; continuous retention revisions and
complete retirement callback composition remain OPEN.
