# Inactive retirement using retained floor images

Status: locally integrated storage path; Phase 2 remains **OPEN**.

## Capacity issue and representation

Two generations and two original sources occupy four image slots. A four- or
five-voter governing floor requires three copies, occupying all seven slots.
The earlier complete physical backup attempted to reserve an eighth image before
retiring the inactive generation, so this otherwise valid maintenance state could
not progress.

The owner now uses the existing complete backup whenever its image reservation
fits. If that image count would exceed seven, it may retain all non-image original
files (including the exact old `source.gscp`) and borrow **every** original image
from the already retained local floor copy. Every borrowed image must match its
original name, length and hash. No semantic-equivalence fallback, mixed image
mode, hard link or extra image file is created.

The private bounded `retirement/images.json` binds the original retirement record,
root/node/storage, active selector, exact floor and local floor-copy generation,
and sorted original image inventory. It counts with the complete saved metadata
against one existing SOURCE reservation. Actual floor images stay charged to
that floor; they are neither a new voter observation nor a free physical copy.

The frozen RETIREMENT record and quorum rules are unchanged. The original saved
backup becomes logically complete through saved non-image files plus the exact
pinned floor images. Missing exact images or insufficient SOURCE/metadata/staging
capacity still refuse before starting retirement.

## Force, deletion and recovery

Force original files as before. Reserve the complete transaction, write and force
the bounded image binding, then all saved original metadata. Re-force the complete
retained floor before writing/forcing RETIREMENT and its parent. Delete only the
unchanged frozen inventory, retaining all current/floor/source identity checks.

A partial binding is an exact request prefix only; it is not deletion authority.
After a complete RETIREMENT exists, missing or changed binding/backing bytes are
not repaired from the old directory. Reopen reconstructs the exact original
materialization from its saved packet/metadata and pinned images, revalidates its
plan and re-forces the backing floor and retirement authority. Even after the old
image has been deleted, no network fetch or new source is needed.

Floor release and other authority changes remain blocked while retirement is
pending. Saved metadata and the binding are cleared only after the old directory
is gone; RETIREMENT clears last. A same-byte live inode replacement still refuses.

## Qualification and limits

See [the local evidence index](phase2-evidence/retirement-images.json) for exact
source/build hashes, original logs, raw snapshots and independent replay.

The final targeted reactor passes **62 Java tests**, including eight new retirement
image tests. Coverage includes old complete-backup compatibility, actual local floor
copies for 3/4/5-voter configurations in old/joint/new views, every file boundary and interrupted recovery,
malformed/missing binding, exact-image absence, floor inode replacement, pinned
cleanup lifetime and exhausted source capacity. A separate case reconstructs the
old packet unchanged when the backing floor has a different packet but the same
exact image. Resource assertions retain the
seven-image/six-source limits and require zero leases after closing each attempt.

The fresh-process matrix has 53 cases and 218 JVMs: nine clean size/view cases,
15 halt/SIGKILL boundaries with the five-node initial view, selected joint/new
boundaries and six repeated recovery crashes. Python reconstructs the original
selection, governing floor, extra original source, retirement inventory, borrowed
binding, force order and physical snapshots. It validates originals before 15
exact-reason mutation rejections and a portable replay, under normal and optimized Python.

Historical membership edges and image contents in this focused storage matrix
remain conditional fixtures. It does not qualify typed public operations,
maximal-byte history, arbitrary pending-context rebinding, repeated high-ballot
progress, network ownership or power loss. The old 549-case receipt continues to
describe its earlier complete-backup implementation; it is not relabelled as a
new-source run.

```bash
python3 -m scripts.v53.retirement_images_qualification <new-evidence-directory>
python3 -m scripts.v53.retirement_images_evidence <new-evidence-directory>/physical
python3 -O -m scripts.v53.retirement_images_evidence <new-evidence-directory>/physical
```

Complete shared lifetime qualification and the offline bootstrap/open paths remain
required before Phase 2 closure. No public runtime, CI workflow or cloud action is
enabled by this change.
