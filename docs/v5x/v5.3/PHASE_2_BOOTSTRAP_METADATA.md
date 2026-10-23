# Phase 2 — original bootstrap metadata without application bytes

Status: locally qualified metadata preparation; **Phase 2 remains OPEN**.
This separates immutable bootstrap description from actual image validation in
preparation for a self-contained local admission record. It does not yet persist
that record or enable complete-store/public opening.

## Shared initial layout

`MembershipBootstrapLayout` derives the original catalog, zero-cut capsule packet,
local counter-one/null-BASIS promise, initial generation manifest, node/allocator,
empty pending slot and selector from exact ROOT/GENESIS plus declared image size.
It returns metadata bytes and a separate image reference. It verifies frame kinds,
original ROOT/GENESIS linkage, nonzero root identities, source rules, supported
ordered 3–5 identities and the frozen resource contract.

`MembershipBootstrapSeed` now uses this shared layout and still supplies and verifies
the actual application image through the capsule verifier. This avoids implementing
another initial-record encoder for metadata-only inspection. It does not remove
actual image decoding, source/codec validation or any ownership requirement.

## Metadata-only plan inspection

`MembershipBootstrapPlanMetadata` reads the exact original plan envelope and checks
its canonical bytes/checksum, root/genesis, declared image identity and size,
application/core/source descriptor bindings, bounded source inventory, exact target
inventories, original path descriptors and declared completion budget. Path strings
must be canonical absolute paths; bindings retain the existing UTF-8 byte bounds
and nonblank filesystem identities. This is a pure decoder and performs no filesystem
writes or path relocation.

The normal `MembershipBootstrapPlanData` decoder delegates these metadata checks,
then separately requires the actual image's exact size/hash and restores its verified
seed/capsule. Metadata decoding alone deliberately cannot establish that the declared
image exists or that any application codec accepts it. It also cannot prove a commit,
local ownership, a vote or a durable force.

## Validation and provenance

[Evidence index](phase2-evidence/bootstrap-metadata.json) retains the source/build
and test receipts. A portable test resource pins six original pre-refactor plans'
ROOT/GENESIS/image references and target inventories from the accepted
[revalidation evidence](phase2-evidence/bootstrap-revalidation.json), commit `6cebcab`.
All metadata bytes for the **24 initial target identities** must match those old
file hashes and sizes; the new encoder does not generate its own expected answers.

Additional regressions compare full and metadata-only plan inspection across all
sizes/sources, check defensive copies, reject changed original bindings/inventories
and invalid bounds, and demonstrate that an accepted metadata declaration cannot
replace verification of actual image bytes. The full source projection, plan and
typed revalidation gates are also run, and their independent original-first replays
remain required. The first build had a test-helper type-name typo; the next run exposed a trailing
fixture newline and a test that tried to mutate an immutable descriptor. Their
failed logs are retained. All **29 tests** passed together on the final inputs,
with **35 exact-reason negatives** across the three independent replays.

No frozen GSER/GSRP/GSBP bytes or public API are changed. The private plan decoder
now rejects malformed path descriptors directly rather than waiting for filesystem
rechecks. Self-contained local admission metadata, existing MISC-budget accounting,
complete-store opening, post-runtime result reading and integrated process
qualification remain next. No protected CI, cloud, power-loss or Phase 2 closure
claim is made.
