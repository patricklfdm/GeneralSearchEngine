# Phase 3 — prepared learner generation and successor reception

The [A17 contract](PHASE_3_CONTRACT_AMENDMENTS.md#a17--prepared-learner-generation-selection-and-bounded-refresh)
adds a durable selection of the [typed learner](PHASE_3_LEARNER_TYPED.md)'s original
nonvoting source. This makes the unique receiving slot available for a successor
without losing or double-accounting the retained source.

The owner reserves a generation count before writing a marker, forces the exact
original selection and directory, and then atomically reclassifies the existing
lease. Original files, file locks and image reservations remain owned. Capacity
refusal occurs before the marker is created. A cancelled pending claim keeps all
original receiving reservations. Pending claims cannot be stolen by another
reservation, even at exact byte capacity.

Refresh accepts only the same live parent's resource pool. It acquires ROOT,
certified prefix, images and complete source generation and checks the original
reservation plus an authenticated connection to the earlier terminal anchor.
Older, foreign or merely higher-indexed histories do not qualify. Repeated calls
cannot use initial admission to overwrite the original plan. The current API
returns a verified successor copy; installation and retirement are still pending.

Reopen requires original sidecar bytes and semantic revalidation. It initially
accounts the source as LEARNER and only reclassifies after the original selection
is forced again. Partial marker recovery requires an exact original prefix; a
complete or partial marker never independently grants votes or readiness access.
The sidecar metadata maximum is 1,460 KiB under the existing 2 MiB MISC lease.

## Focused validation

Component tests cover all five joining shapes, seven selection interruption
positions, exact-capacity claims, cancellation, concurrent reservations, original
byte preservation, semantic reopen, owner revocation and missing ancestry proof.
Synchronous exceptions are not process-death qualification.

The native smoke uses one original 600-second test deadline, real TCP voters and
five certified slots: BARRIER, RESERVE, PREPARE revision 1, PREPARE revision 2 and
CANCEL. It keeps the first selected learner live while receiving the successor,
asserts simultaneous GENERATION/LEARNER ownership, then closes the successor and
checks that the original still owns its bytes. Both complete client acquisitions
must match the entire server trace in the independent physical replay. No READY,
INTENT, public voting or successor installation is claimed by this history.

Final source evidence and attempted runs are recorded in
[the qualification receipt](phase3-evidence/learner-prepared.json). Process death,
successor installation/retirement, all seven transitions, autonomous continuation
and combined maximum-headroom acceptance remain in the
[deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Phase 3 remains OPEN.

## Retained source distinctions

The native history passes in 277.5 seconds (381 seconds including its component
suite and compilation), with 31 exchanges and nine original files in each of the
two acquisitions. Original physical replay rejects all ten exact evidence
mutations. The previous typed READY history also replays unchanged after the
shared reader extraction. All 771 V5.3 Python tests pass.

The final review adds an exact source-lease identity guard across three production
files, preventing a forced selection from consuming another store's claim. That
review passes 24 component methods on a separate immutable snapshot, including
received-owner and reopened-owner regressions. Portable optimized replay also
passes all ten exact negatives. The native evidence retains its earlier source identity;
final-source full native/process matrices remain due in hosted acceptance. No
production time or resource ceiling was increased and no cloud job was launched.
