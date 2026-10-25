# Admitted old / joint / new configuration storage

Status: locally qualified for these four storage profiles. This batch connects actual public offline
bootstrap to local configuration-aware storage. It does not enable a membership
runtime, learner, network exchange or public add/remove operation.

## Fixed profiles and originals

`V53AdmittedCrossViewTest` starts four independently provisioned groups: five and
four initial voters, each from EMPTY and a verified typed backup. The initial
ROOT, history, storage identities, node admissions and bootstrap result remain
unchanged throughout each profile. Every observed ACCEPT, PROOF and checkpoint
ACK comes from opening the corresponding admitted owner and forcing its actual
record. The producer retains complete byte snapshots after every phase.

Five-voter groups execute REMOVE 5→4 and then REMOVE 4→3. Four-voter groups
execute REMOVE 4→3. Each transition publishes RESERVE, PREPARE, READY, SEAL,
INTENT and FINAL, obtains a fresh stable-view selection, publishes a BARRIER,
and retires terminal operation detail. A final typed DATA and BARRIER check
the unchanged history and one application-sequence increment. This is 60 slots,
232 individual owner publications and six removals; these are local storage
operations, not distributed runtime commits.

The independent reader derives the complete catalog, source groups, selections,
phased votes, checkpoint ancestry, application images, generation manifests,
selectors and retained inventories from original bootstrap bytes and the fixed
command sequence. It checks both governing majorities, exact observations and
force-before-return ordering, including the removed owner's fence before adoption.
Original validation precedes negative mutation, and relocated evidence must replay
without the original producer workspace.

## Bounded orchestration

An INTENT ends the stable round. Its original first proven endpoint can be hidden
inside the preceding RANGE, so the publication retains that original checkpoint
proof. It does not manufacture a RANGE spanning the membership edge. A fresh
joint selection exposes the necessary old cuts directly; unused old round proof
does not become installation authority.

The surviving voters form both the old and new majorities. They capture and
install the joint selection, publish FINAL, and perform floor/source maintenance
within the frozen seven-image limit. The removed voter retains the original
INTENT generation, then adopts the complete certified FINAL. Adoption forces the
newer null-BASIS promise before its selector. Duplicate adoption is byte-identical;
a fresh PREPARE from the removed identity is refused without modifying its files.
Its original source and inactive generation are retained, not silently deleted.

This route is intentional. Capturing and installing the joint ballot on every old
voter caused the soon-removed five-voter owner to require four floor copies: its
own copy plus three new-side voters. Together with two generations and two
original sources that would consume eight images. The unchanged storage owner
refused this operation. The successful route must not be interpreted as permission
to increase the image limit, omit the local floor copy or weaken either majority.
Automatic scheduling of these operations belongs to later protocol work.

## Evidence and limits

Retained work directory: `target/v53-admitted-cross-view/`; the
[source/build/evidence index](phase2-evidence/admitted-cross-view.json) binds the
original bytes and immutable producer classes. The one Java matrix test completes
all four profiles in approximately 16 minutes. Sixteen focused Python tests pass;
normal and assertion-disabled replay require the same 16 named rejections and
portable replay result. The image peak is seven in every profile. All 707 production
classes and the two production JARs remain identical to the corrected mixed-context
runtime retained by [that batch](PHASE_2_COVERED_CONTEXT_MIXED.md).

The independent application check parses actual core metadata, checkpoint and
manifest bytes, including CRCs, content identity, document order and the fixed
fixture codec. DATA sequence and document mutations have valid checkpoint CRCs;
they must be rejected for their semantic mismatch, not incidental CRC damage.

Earlier unsuccessful
producer attempts remain there with their exact source maps and raw inventories:
the first omitted the original hidden endpoint proof, and the second exceeded
the image count on the soon-removed joint participant. Neither is a passing
qualification. A mistyped Python test-module invocation also remains recorded.

This matrix uses ordinary-sized images and repeated owner close/reopen within
one producer JVM. It does not establish process-death recovery, maximal bytes,
ADD/REPLACE learner eligibility, network liveness or a power-loss guarantee.
Those claims require their own evidence. The Phase 2 closure audit and remaining
maximal-resource qualification stay open.

## Shared fixed-fixture image reader follow-up

The independent `OfflineApplication` backup decoder now lives in
`scripts/v53/offline_fixture_image.py`. It retains exact history, sequence, profile,
codec, index, ordered document, manifest and content-identity checks. A table-based
CRC32C implementation is checked against the existing bitwise decoder and the
standard check value. This is a reader for this fixed test fixture, not a general
production backup importer.

The unchanged retained four-profile evidence was replayed with normal and
optimized Python. All six removals, 60 slots, 16 original-first evidence mutations
and portable replay remain equal; 20 focused Python tests pass in both modes.
The [follow-up index](phase2-evidence/offline-image-reader.json) records the new
reader hashes and results. Original frozen producer evidence and its source files
remain intact. No Java workload was rerun for this extraction, and maximum-image
qualification remains a separate pending batch.
