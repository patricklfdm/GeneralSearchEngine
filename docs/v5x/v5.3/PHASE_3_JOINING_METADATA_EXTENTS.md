# Phase 3 joining metadata extents

This composes [original request bindings](PHASE_3_JOINING_EXPORT_REQUESTS.md)
with [export ownership](PHASE_3_SESSION_EXPORT_OWNERSHIP.md). The
[development index](phase3-evidence/joining-metadata-extents.json) retains the
checks. Phase 3 remains OPEN.

## Original content determines the reservation

The new reader derives expected metadata charges from complete original
transfers already admitted by the physical/network/content/maintenance readers.
It binds each result to the exact first framed request, original source node and
session allocation. Equal sizes or a matching role name cannot establish that
association.

| Metadata family | Expected CONTROL bytes |
| --- | --- |
| joining retention | Three 2 MiB fragment capacities: 6 MiB |
| joining preparation | Two 16384-byte hint capacities: 32768 |
| joining completion | Two 16384-byte hint capacities: 32768 |
| pending INTENT | 65536 + four times the sum of original ENTRY, ACCEPT, PROOF, CERTIFICATE, CATALOG, CHECKPOINT and payload byte lengths |
| pending joining checkpoint | Length of the original framed CHECKPOINT_ACK |

The INTENT calculation decodes the exact six framed originals and the canonical
Base64 payload; it does not use encoded-container length as the reservation.
The 8 MiB metadata frame limit remains distinct from the 4 MiB chunk limit.
Checkpoint recognition requires the independently reconstructed pending ACK;
another ordinary ACK export does not become a joining checkpoint export.

Retention and INTENT also require their exact nested 4096-byte prefix reservation.
Its binding comes from the original generation manifest active throughout the
observed transfer interval. Metadata and prefix handles remain distinct. Existing
ownership replay requires immutable charges, exclusive session ownership and
normal cleanup. The new gate checks complete expectation coverage and refuses
extra or missing original sessions.

## Native entry and scope

Use the existing native resource entry with all its prerequisites:

```bash
python3 -m scripts.v53.native_resource_evidence "$RAW" \
  --profile 5-REPLACE-required-four \
  --source-control --control-closes --export-ownership \
  --joining-requests --joining-extents
```

Physical publication, required-four network/content/maintenance and original
source-buffer replay must succeed before extent checks can contribute a result.
Missing export observations retain their PARTIAL status. This gate does not
replace probe/rollback qualification or establish whole-runtime physical peaks,
custody or final-source qualification.

The conditional handler reader has a separate entry:

```bash
python3 -m scripts.v53.joining_metadata_extents "$COMPONENT" --qualify
```

Its exact inventory retains the first request, resource/cleanup observations and
actual returned content; retention additionally retains its original generation
manifest. These fixtures do not acquire native membership authority. Their outer
receipts always remain PARTIAL, including after negative qualification.

## Evidence retained in this batch

- Eighteen new Python tests and adjacent readers: 196 tests pass. They cover all
  five formulas, original frame decoding, exact request/source/family bindings,
  nested generation/extent, missing ownership and prerequisite failure. Synthetic
  cases remain unit evidence.
- Twenty-two focused Java tests pass. The two existing real handler tests now
  additionally retain their exact returned bytes in separate collections, leaving
  the earlier request-only collection format intact. The new actual retention
  and preparation collections both pass independent accounting replay and 16
  exact negatives. Unmodified originals must pass before mutations.
- The retained required-four original passes physical/network/content replay.
  The new derivation covers eleven metadata sessions: two INTENT, three pending
  checkpoint, one preparation, three retention and two completion. Replay and
  derivation took 153.604 seconds locally. This historical capture has legacy
  allocation bindings; it is not rewritten or counted as a current-source full
  resource qualification.

Logs, copied JUnit reports, original capture paths and source hashes are retained
under `target/v53-joining-metadata-extents/`. Production Java, quotas, wire/storage
formats, workflow behavior and frozen coverage are unchanged. No new long native
history or hosted run was executed.

Complete current-source joining/required-four resource composition, other
failure/cleanup paths, physical custody/peaks and final-source hosted admission
and execution remain open. The plan still has twelve review requirements and
544 planned hosted histories; Phase 5 owns the 3310 S cases.
