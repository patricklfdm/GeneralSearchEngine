# Streaming retirement and publication observations

The [grant streaming work](PHASE_3_GRANT_STREAMING.md) is now extended to the
source-retirement and publication-resource object pools. Explicit verified-backup
segmented callers retain the existing schemas, event binding, exact force order
and independent comparison. Existing JSON callers retain their 256 MiB limits
and eager reader behavior.

## Capture and replay

`V53CaptureFiles.ObjectStore` writes through a 1 MiB buffer, reuses identical
content-addressed objects and verifies existing objects before reuse. It checks
the original snapshot after capture, rejects unexpected pool members and keeps
writer descriptor custody. A truncated or corrupt destination is retained as
failed evidence, never published as a successful capture. The native joining
helper and publication observer propagate the caller's explicit source/layout.
No observation grants an authority, extends a runtime lifetime or releases a
production reservation.

`capture_objects.Pool` checks every bounded object and retains identities, sizes
and hashes. Immutable prefix mappings share that pool and load only requested
files. Comparisons stream selected original objects and compare their checked
metadata to independently expected bytes. Directory membership, identities and
unread objects are checked at collection boundaries. Complete validators still
check the whole original before and after replay.

Retirement's established independent oracle uses a `bytes` extent field; capture
metadata uses `size`. The adapter converts the checked metadata into the unchanged
oracle shape. Publication's exact reservation and boundary comparisons are
unchanged. Caller policy reaches required-four physical replay, export windows,
learner handoff, native resources, complete resources and publication negatives.
Capture metadata never selects its own admission policy.

The bounds remain explicit:

| Boundary | Segmented capture policy |
| --- | --- |
| Individual object | 64 MiB |
| Objects per pool | 8192 |
| Members per prefix / path depth | 512 / 8 |
| Logical bytes per replica prefix | 512 MiB, the current physical snapshot ceiling |
| Retirement / publication captures | 512 / 1024 |
| Unique pool bytes | At most the existing 128 GiB **shared whole-original** allowance |

The whole-original cap also includes grant copies, wire segments, metadata and
all other retained families. It is not an independent budget for each pool.
Runtime metadata, image-count, staging, queue and lifetime limits are unchanged.

## Evidence

The [development index](phase3-evidence/capture-objects-development.json) records
source hashes, logs, original identities and the following distinct scopes:

- A fresh three-owner verified-backup writer executes one new BARRIER publication
  per owner and retires the prior sources on the next campaign. Its 45 retirement
  prefixes and 33 publication boundaries pass both collections with identical
  bytes. Separate JVM probes confirm the writer locks remain held. This is an
  orchestrated writer component, not a TCP/joining/final-source qualification.
- A retained complete EMPTY original has 330 retirement and 374 publication
  prefixes. Legacy and deferred collection agree exactly; the original remains
  EMPTY and is not reclassified into a backup cohort.
- A separate original source-retirement component passes the unchanged independent
  transaction derivation for all 15 prefixes and twelve exact negative mutations
  using the new pool reader. Publication model fixtures retain all 26 exact
  negative reasons. These checks do not replace full native history derivation.
- Five distinct synthetic 64 MiB objects are written, deduplicated and checked
  with a 32 MiB Java heap. A 320 MiB Python pool and 1024 shared prefix views
  pass under a 160 MiB address-space ceiling. These are object-pool components,
  not valid maximum application images or whole-reader memory measurements.
- Final Java selection: 15 tests passed, including the old publication helper's
  six size/source combinations. Final focused Python selection: 879 tests passed.

Failures remain visible. The original publication helper also verifies an
idempotent second call; the first new fixture therefore retained 39 boundaries,
including six short-path observations. The complete-publication reader correctly
rejects that original. The corrected fixture explicitly uses `publishOnce`;
the old helper still performs its idempotency checks. No captured rows were
removed or stitched into the corrected original.

The first independent retirement replay exposed the `size`/`bytes` adapter
mismatch described above. The unchanged original passes after the correction,
and a regression protects the established oracle format. A negative-driver unit
fixture also initially omitted its `events.json`; its failed log and corrected
test are retained. None of these failures is reported as a runtime protocol fix.

## Next requirements

The current 512 MiB physical snapshot ceiling is not proof of a maximum native
owner's admissible extent. The frozen metadata reservation arithmetic alone is
324 MiB; seven 64 MiB application reservations add 448 MiB. The separate retained
log contract must also be examined. These categories are not proof that all peaks
are reachable together. Before the maximum execution entry is accepted, derive
the actual physical inventory bound and its transient copies from the frozen
contracts and owning implementation; do not choose a larger cap arbitrarily.

Semantic derivation may still materialize application images. Whole-reader memory,
the maximum-image native composition, simultaneous ownership/refusal boundaries,
the complete default-staging history with 150 negatives and the immutable final-
source cohort remain pending. All five Phase 3 closure gaps remain open. The
operator currently has no qualified native Linux maximum-image host; development
continues, with formal execution to be arranged later and its environment checks
preserved.

Rollback removes the explicit object-store policy and its propagated reader
arguments together. Old JSON behavior, schemas, retained originals and frozen
production bounds remain available. No production Java, POM, workflow, paid-cloud
operation or V5.2 evidence changes in this batch.
