# Explicit staging policy for native backup qualification

The [frozen resource contract](RESOURCE_AND_LIFETIME_LIMITS.md) keeps a 16 GiB
default snapshot-staging allowance. Existing native development histories use a
smaller 512 MiB fixture allowance. These are distinct caller configurations; an
artifact cannot select which configuration a verifier admits.

This distinction is a prerequisite for the remaining maximum-image/native
composition. The conservative accounting envelope can reserve 192 MiB for six
SOURCE capsules, 32 MiB for one LEARNER capsule and 448 MiB for seven application
images: 672 MiB staging. That arithmetic exceeds the small fixture's allowance.
It does not prove that every category maximum is simultaneously reachable on
one legitimate native owner. The earlier [external-copy pressure failure](PHASE_3_COMBINED_RESOURCE_PROBE.md)
remains failed and cannot establish such reachability.

## Capture policy

`V53NativeResourceProfile` offers two explicit test-only choices:

| Profile | Staging allowance | Admission |
| --- | --- | --- |
| `SMALL_FIXTURE` | 512 MiB | All existing fixture constructors and histories retain this default |
| `DEFAULT_SNAPSHOT_STAGING` | `ReplicationBounds.defaults().maxSnapshotStagingBytes()` = 16 GiB | Caller must supply verified-backup source and segmented wire layout |

The selected profile follows the bootstrap fixture, native old-voter budgets,
late joining budget and resource-transition capture. Every resource journal
records its actual configured limit. All metadata, queue, count, application
image and completion reservations remain unchanged: seven application images,
six SOURCE slots, one LEARNER, 384 MiB metadata and 64 MiB aggregate queue.
The ordinary full backup execution entry still selects `SMALL_FIXTURE`.

The full required-four helper accepts the profile explicitly; it does not read a
new environment switch or infer policy from backup contents. The legacy JSON
resume constructor and legacy export-probe fixture reject the new profile rather
than silently reopening with the smaller budget. A future maximum-image entry
must use the explicitly admitted lifecycle and retain its own original evidence.
The new network constructor also rejects caller transport bounds whose staging
allowance disagrees with the selected default profile, before bootstrap or
preparation starts.

## Independent replay and rejection

`native_resource_policy.py` fixes the same two caller profiles. Default low-level
resource and learner-handoff replay still require exactly 512 MiB on every owner.
An explicit `DEFAULT_SNAPSHOT_STAGING` caller requires exactly 16 GiB on every
owner, including the joining node. Mixed pools, arbitrary limits and changed
limits are rejected. Complete replay permits this choice only with the verified
backup, segmented layout and five-voter required-four history.

`required_four_resources.qualify_default_staging_backup` runs the complete
physical/semantic/network/resource original and then the existing negative
families under the same explicit policy. Its separate schema/profile require
150 exact negatives: the previous 149 plus rejection by the default small-pool
reader for `native resources original limits`. An unrelated failure or acceptance
by that reader cannot count. Top-level, original-accounting and learner-handoff
receipts bind `resourceProfile` and `stagingLimit`. Existing EMPTY and small-backup
entry points keep their schemas, 147/149 cases and limits.

This gate still qualifies observed ownership only. Changing the fixture's
declared staging allowance neither proves a maximum physical peak nor satisfies
combined-resource, final-source or Phase 3 closure. The current hosted
[small-backup workflow](PHASE_3_BACKUP_HOSTED.md) remains unchanged and cannot
transport/admit this profile as its own member.

## Evidence and next work

The [development index](phase3-evidence/native-staging-development.json) records
configuration/accounting tests separately from short TCP seed evidence and its
independent resource replay. The accounting reservation test allocates no image
files and is not a physical maximum. A short first-BARRIER history is not a
complete joining, FINAL, handoff or 150-negative qualification.

The actual short default-profile original records all five old-voter budgets at
16 GiB, application sequence 731 and first BARRIER index 1. Independent catalog
and resource replay, 15 original-derived accounting negatives and exact rejection
by the 512 MiB reader preserve the original bytes. The old EMPTY and small-backup
seed checks also pass. These are development observations, not a final-source
cohort or a claim that all categories were simultaneously full.

The remaining work is to bind a maximum-image execution entry and its complete
capture/transport, declare permitted same-owner pressure/refusal/continuation
boundaries, check whole-reader memory, and execute the final complete histories.
The [grant-copy path](PHASE_3_GRANT_STREAMING.md) and
[retirement/publication pools](PHASE_3_CAPTURE_OBJECTS.md) now have explicit
streaming capture/replay. The [segmented replica envelope](PHASE_3_REPLICA_CAPTURE_ENVELOPE.md)
now consistently allows 832 MiB; actual maximum physical composition and
whole-reader memory remain unqualified.
Neither separate component peaks nor artificially extended receivers may be
combined into a success claim. Rollback removes the explicit profile and new
gate together; old fixture defaults and retained originals remain intact.
