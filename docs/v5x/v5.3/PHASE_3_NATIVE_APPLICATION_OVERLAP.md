# Native application recovery: simultaneous physical owner counts

Phase 3 remains **OPEN**. This supplemental reader derives physical overlap from
an existing complete application-ACK crash/recovery original. It adds no native
producer, hosted subset or source-cohort admission. The twelve-subset catalogue,
all frozen resource limits and all existing verification commands are unchanged.

## What the reader establishes

`python3 -m scripts.v53.native_application_overlap` first replays the complete
nine-family original using the [application capture adapter](PHASE_3_CARRIED_APPLICATION_COHORT.md).
The original protocol, captured files, resource transitions, exact owners and
close boundaries must pass before any overlap result or negative receives credit.
The case must match the original INTENT/FINAL and halt/SIGKILL identity.

For every captured callback, the reader reconstructs that owner's live charges
through the recorded resource sequence. It re-derives physical ownership from
original file paths and transaction-specific image ordinals, then compares that
inventory and usage with the original physical verifier's snapshot. Each witness
retains its node, lifetime, event index, callback, sequence, inventory hash,
snapshot hash and complete resource-trace hash.

A count witness requires **two GENERATION, six SOURCE and seven APPLICATION
owners with nonempty physical files at the same callback**. Empty directories,
zero-length files and reservations without files cannot supply a physical count.
Identical image contents at different owned paths remain separate copies.
SOURCE here is the storage category: a retirement or FLOOR owner is not another
selected voter or necessarily another complete grant capsule.

Physical bytes, metadata, application bytes, staging bytes and reserved amounts
are reported separately. Each peak selects one complete original callback,
including the other measurements at that same point. Peaks from different
callbacks or owners are never summed. The configured shared limits and unspent
protected completion headroom accompany each witness; a category's reservation
ceiling is not its observed file extent.

Twenty exact negative checks cover altered scope, counters, original owner and
lifetime identities, event sequences, empty-file counts, identical-copy
deduplication, mixed peaks and substituted inventory/trace hashes. These mutate
**derived witnesses in memory**, not original files. They supplement the existing
physical negative catalogues and do not replace them. An invalid original or an
original without a simultaneous count witness cannot earn those rejections.

## Reproducing the supplemental check

Use a complete application-ACK original, not its compact receipt, and a fresh
output directory:

```bash
python3 -u -m scripts.v53.native_application_overlap \
  target/v53-carried-application-custody/qualification/final-kill \
  --case final-application-kill \
  --output target/v53-native-application-overlap/manual-replay
```

The command emits a progress line every minute, preserves a failure receipt, and
refuses to overwrite an existing output directory. It rechecks the input
inventory after validation and negative qualification. The result is `PARTIAL`;
no new JVM or cloud experiment runs.

## Development evidence and remaining obligations

The retained FINAL/SIGKILL original belongs to the recorded `7e63a097` development
snapshot plus its explicit custody correction. Replaying it does not qualify the
current source or substitute it into the final-source cohort. The actual replay
result is indexed in `phase3-evidence/native-application-overlap-development.json`.
The focused tests are synthetic guards; they are not native executions.

The fresh original replay passed in **113.071 seconds**: 3,301 callbacks across
eight owner lifetimes, 176 simultaneous nonempty count witnesses and all twenty
exact negative rejections. The first count witness is life 1, `node-1`, callback
969 (`RETIREMENT_BORROW_PREFIX_WRITTEN`), resource sequence 1,144. Its actual
files total 405,475 bytes; its seven application copies total only 5,859 bytes.
The largest complete observed callback totals 628,258 physical bytes, at life 2,
`node-2`, callback 2,229. These small extents cannot establish the full byte bound.

A separate calculation from the previously validated owner snapshots agrees
with the new original replay. It finds 268 callbacks with charged counts 2/6/7,
but only 176 with matching nonempty physical owner counts; the other 92 are not
credited as physical saturation. All 10,599 original files (80,274,926 bytes) and
all 527 preceding evidence indexes remain unchanged. The complete bounded result
is 80,322 bytes. All 69 related Python tests pass, including the fifteen new
selection/admission tests; those fifteen also pass with assertions disabled.

This closes the missing *measurement of simultaneous nonempty count overlap* in
that development history only. It does not establish full metadata-byte pressure,
shared staging-byte saturation, at/over-bound refusal, an admitted learner's
combined lifetime, or completion of the full operation-231 capacity continuation.
The existing [receive-boundary histories](PHASE_3_COMBINED_RECEIVE_RESOURCES.md)
and [capacity continuation](PHASE_3_CAPACITY_COMPLETION.md) retain their distinct
scopes. Further native evidence must compose those remaining obligations on a
feasible original history before combined resource qualification can close.

Rollback removes this supplemental reader, its tests and these current links;
retain all earlier originals, failures, runtime fixes and source-bound entries.
