# Phase 2 — compact original bootstrap admission data

Status: **private metadata decoder qualified locally; Phase 2 OPEN**. This batch
adds no store opener and no new file to the bootstrap transaction.

## Original bytes and verification

The private GSBP 1.3 kind 5 container contains three length-prefixed original
frames: the coordinator receipt, COMMITTING and COMMITTED decisions. Its 48-byte
header/checksum and complete body are bounded to **65,536 bytes**. It is binary,
not the JSON body used by private kinds 1–4, and does not change GSER/GSRP catalogs.
There is no copy of the full plan, application descriptor or initial image.

`MembershipBootstrapAdmissionData` checks this container against the existing
original ROOT, GENESIS, local preparation and local seal. It checks:

- Exact expected root, full local identity, authority and materialization paths.
- The initial inventory derived from original ROOT/GENESIS and declared image
  size, including every initial metadata byte hash and the image reference.
- The local preparation hash at its original position in the receipt.
- Exact COMMITTING/COMMITTED bindings and all ordered initial target identities,
  canonical common path anchor, local paths and pairwise disjoint target paths.
- The original seal's preparation/receipt hashes and local identity/path binding.

Header/length checks precede the bounded copy. Embedded frames retain their own
syntax/checksums. Missing, truncated, reordered, trailing or mismatched bytes are
rejected. Returned bytes are defensive copies. Decoding does not read coordinator,
source or application files, acquire ownership, validate typed application
semantics, force anything, or grant voter eligibility.

The other voters' full preparations are not copied to this local record: their
original hashes remain in the receipt. This is integrity checking under the
existing non-Byzantine disk model, not independent proof of another process's
force. A self-consistent computed record cannot prove bootstrap occurred. Actual
admission still requires the future exclusive store owner and the qualified
transaction publication order; public bootstrap/runtime remain disabled.

## Retained validation

[Source/build evidence](phase2-evidence/bootstrap-admission-data.json) records the
final Java/Python inputs, compiled JARs/classes, logs and raw inventory.

- **15 Java tests**: five new decoder tests plus ten shared-layout/commit metadata
  regressions. The first compile failed on wildcard-list mutation in a negative
  test; the log remains retained. The corrected final run passes.
- Real EMPTY and verified-backup transactions at sizes 3/4/5 produce **24 original
  committed local targets**. Derived admission bytes are retained separately from
  these stores. Decoder calls leave original transaction files unchanged.
- Foreign histories/identities/paths, rehashed inventory/decision mismatches,
  corrupt envelopes, impossible section lengths and duplicate/reordered frames
  refuse. An escaped 4,001-byte absolute parent path still fits the compact bound.
- An independent Python replay re-derives actual image-backed original transaction
  bytes before checking each derived admission. **15 exact evidence negatives**,
  normal/optimized execution and relocated replay must agree. Unmodified evidence
  passes before any negative is counted.

No new crash point or power-loss guarantee is claimed by this data-only batch.

## Storage integration obligations

The next transaction must write one exact-prefix admission file after COMMITTED,
force file and parent, then publish the final local seal. A seal candidate or
active seal must require a complete original admission file; missing admitted
bytes cannot be reconstructed from arguments. The full operation budget must
include one admission per target before its first write. No second full admission
copy belongs in the runtime peak.

The existing 2 MiB MISC reservation is shared, not increased. A conservative
candidate source-retirement peak is 2,080,768 bytes: root/genesis/node maxima;
two allocator and two selector records; preparation/seal/admission at 64 KiB each;
1,138,688-byte source-retirement decision; 565,248-byte compact journal; 32 KiB
floor proposal/floor; 28 KiB capture decision; 16 KiB applied-end retirement.
This leaves 16 KiB. The integrated audit must still establish all categories,
maximum-profile completion and mutually exclusive maintenance states; a sum alone
is not closure. Source retirement already refuses inactive generations, pending
floor release and generation retirement. Context/accept authority remains charged
to JOURNAL, with generation/source/image copies retaining separate reservations.

Complete-store opening must validate these bindings instead of whitelisting
bootstrap filenames. Post-runtime result inspection must tolerate legitimate
mutable allocator/journal/generation changes without treating missing immutable
admission as a reason to repair. Extended write/force/recovery and fresh-process
qualification remain pending, along with the other Phase 2 lifetime obligations.
