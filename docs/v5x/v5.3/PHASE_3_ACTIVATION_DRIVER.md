# Phase 3B — bounded outgoing activation driver

`MembershipActivationDriver` owns one current-view outgoing activation invocation.
It connects the already-qualified incoming endpoint, original-source transfer,
fixed selection and durable installation. Its caller invokes `run()` once on the
runtime's serialized control path. Bounded peer workers make network progress
concurrently; only the caller consumes complete sources and installation ACKs.
The returned selection is not public READY and does not enable an election timer.

## Selection, retries and fairness

The local original grant is forced before any PREPARE. The endpoint serves its
actual original PROMISE before peers may request it. The driver starts a minimal
eligible peer set concurrently, including the local proposer in both old/new
majority calculations. Another eligible peer receives an opportunity if an initial
peer fails or consumes one existing request timeout. Only complete verified source
packets participate in the first eligible fixed quorum; a fast PROMISE by itself
cannot win selection.

A failed selected remote installation abandons the ballot. On the next fresh
ballot the driver prefers an eligible set excluding that failed peer, then falls
back after the alternatives fail or consume their bounded opportunity. It cannot
replace a selected source at the same ballot. Each exact control exchange retries
only transport I/O/deadline failures, at most three times or the caller's stricter
limit. Corruption, foreign replies and cancellation are not retried. Bounded
capacity/NOT_READY failures can select another peer or start a fresh ballot.
An authenticated higher promise fences immediately, before waiting for a writer;
that invocation ends rather than competing indefinitely at ever higher ballots.

All campaigns, source pulls and control retries inherit **one original start and
deadline**. A fresh campaign checks that budget before durable allocation, including
time spent waiting for the writer. No successful result can be returned after
expiry, cancellation, source invalidation or an observed higher ballot.
A deterministic regression first demonstrated that checking only before entering
the writer monitor could still force a grant after the budget expired in that
wait. The correction rechecks inside the monitor before allocation. The original
failed storage-hash comparison is retained alongside corrected validation.

## Installation and ownership

All selected remote installations must return the exact selection/cut ACK before
the proposer installs locally. A lost remote ACK may leave that remote generation
installed; it is retained and never rolled back by the driver. A local installation
failure is terminal for this invocation, requiring journal recovery/maintenance.
The driver cannot turn it into a peer failure and retry blindly.

The journal, incoming endpoint, transport and driver use the same resource account.
Original local images may be borrowed only through the existing pinned physical
export checks. Missing images still require receiving reservations. The first
selected source files remain owned until all installations finish. Nonselected
workers are cancelled and drained before installation; every worker is drained
before another campaign starts. Close cancels pending exchanges and removes only
owned scratch, preserving and reporting foreign files. Failed cleanup remains
retryable; it cannot yield an installed selection or authorize a new campaign.

One invocation accepts an explicit caller campaign count, bounded by six, and can
fail earlier at the unchanged source/image/metadata limits. Failed rounds' durable
original sources are **not deleted to make retries fit**. This count is a private
work bound, not a new public resource limit or a claim of indefinite recovery.
The later runtime must connect governing-floor maintenance and restart recovery.
The successful endpoint scope remains available until expiry, fencing or driver
close; callers must still perform the carried entry and stable service barrier.

## Qualification

The [local receipt](phase3-evidence/activation-driver.json) records the final source,
96 Java tests across eleven suites (twenty driver tests), 564 Python tests in
both modes, original physical replay and ten exact negative variants. The final
trace contains 156 source exchanges, ten controls and eight actual installations. Actual TCP stable-3/4/5 histories use automatic outgoing PREPARE, complete
source delivery, fixed selection and every selected installation. Independent
replay derives expected records, full images and installed files from original
bootstrap/journal bytes. Concurrent control delivery is correlated by its original
sequence; neither missing nor duplicate controls are accepted. This test profile
uses the default 4 MiB transfer chunk limit and exact pinned local image reuse;
older 1 KiB replay profiles retain their original parameters.

Deterministic owner/endpoint tests cover transient identical retries, alternate
sources, a failed selected installation, lost installation ACK, deferred-peer
fallback, stalled sources, all-selected ACK gating, higher-ballot rejection,
late ACK fencing, cancellation during source staging, caller campaign exhaustion,
foreign scratch and original deadlines. All seven transition profiles exercise
both-majority scheduling arithmetic; this does not claim their actual distributed
learner/transition qualification.

## Remaining Phase 3 work

Historical provenance and compacted ancestry delivery, root-bound newer-view
STATUS/discovery/adoption, restart cleanup of abandoned receiving scratch, durable
source retirement during repeated campaigns, real learner/joint transitions,
carried voting/publication, election ownership and complete network/process S/N
qualification remain open. Phase 3 is not closed. Public automatic membership,
protected CI, paid cloud and released-predecessor integration are not claimed.

Rollback removes this private driver and its original-start constructor/matching
endpoint revocation adapter. Persisted formats, public declarations, workload
parameters, workflow and V5.2 runner behavior are unchanged.
