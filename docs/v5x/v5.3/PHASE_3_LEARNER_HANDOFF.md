# Phase 3 — original learner ownership handoff

The [A20 contract](PHASE_3_CONTRACT_AMENDMENTS.md#a20--forced-learner-ownership-handoff-before-physical-retirement)
adds a durable handoff from the live predecessor/current typed pair to a separate
parent-owned source view. Its original record binds the selected source, current
receipt and every original typed member's bytes and filesystem identity.

Both typed owners must remain valid through the handoff writes and forces. A
close or mutation during those cuts fails without deleting originals. After the
active head and directory are forced, the two typed handles close and remain
revoked. A fresh source view can then survive those child closures while the
parent is live. Its source is still nonvoting; typed readiness requires a new
semantic reopen against the original current backup and compact plan.

Reopen accepts only the original complete active head. A complete candidate can
resume only after explicit matching typed preparation. Incomplete records,
unknown members, changed fingerprints and source/receipt mismatches are retained
and refused. Head files use bounded sorted path/hash rows, fitting inside the
original 2 MiB MISC budget without increasing any resource limit.

This is the durable prerequisite to physical retirement. It deliberately retains
both sources and both backups; no lease is released for bytes still present.
Source recovery still requires the original files. The next implementation must
teach recovery about the forced retirement decision, delete only its exact
covered originals, force deletion parents, release the corresponding reservations
and reuse the bounded generation slots. This batch does not claim those steps.

Focused results and retained failed builds are recorded in
[the receipt](phase3-evidence/learner-handoff.json). The longer synchronous-cut
class is compiled but deferred; it is distinct from halt/SIGKILL qualification.
Native multi-revision handoff, process-death recovery and the full Phase 3 matrix
remain in the [hosted acceptance queue](PHASE_3_DEFERRED_ACCEPTANCE.md). No hosted
workflow, release or paid cloud experiment is triggered here.

## Retained focused results

The corrected immutable build passes ten methods: three handoff cases, five
existing preparation cases and two resource-owner cases, with zero failures,
errors or skips in 235.1 seconds. It tests exact forced handoff, parent reopen
without reopening the old typed handle, retained-byte accounting, original member
mutation refusal, complete-candidate recovery and predecessor-close revocation
before active commit. The six-point synchronous-cut matrix is compiled but has
not been run in this batch; neither has a new native or process-death matrix.

The first build remains retained with its two failed handoff methods: file paths
were mistakenly encoded as object keys, which the existing strict JSON encoder
correctly rejected before head creation. Sorted path/hash rows fix the shape;
the corrected build also adds live-owner checks throughout forcing. Its source
identity and the first build's one-production-file difference are recorded
separately. Seven unchanged preparation/resource tests passed in that first build.

The original/final sources, compiled-input hashes, Surefire results, commands and
documentation check are archived. Every archive member is checked against its
SHA-256 inventory. This component archive is not independent physical/native
qualification and does not complete Phase 3.
