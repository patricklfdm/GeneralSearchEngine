# Phase 3 store ownership across failed listener drain

This extends [retained-owner drain](PHASE_3_PENDING_LISTENER_DRAIN.md) to its
enclosing learner store. Exact development inputs and results are retained in
the [evidence index](phase3-evidence/store-listener-drain.json). Phase 3 remains
OPEN.

## Reproduced parent release

The old `MembershipLearnerStore.close()` set its one-shot `closed` flag and then
used best-effort cleanup for every child. A pending listener drain failure did
not stop cleanup of the typed owner, replica lock, operation lock or parent
storage. Another store close returned immediately even though the pending child
still needed an external drain.

Four deterministic TCP regressions fail on the original implementation:
checkpoint/head listeners, each closed in their own callback or by an interrupted
external thread. In all four, an independent JVM acquired the original operation,
replica and preparation locks while the response callback remained held. Storage
reservations also dropped. Original failure logs and resource/file/lock observations
remain retained; this is a lifecycle defect, not a timing-based retry decision.

## Two-stage close

The store now revokes itself, then attempts to revoke and drain every owned
disposition listener before releasing child storage or parent locks. Drain runs
outside the store monitor. A failure is propagated with its interrupt state and
keeps the same store available for a later close attempt.

Only after every disposition listener drains does serialized cleanup release
the children, storage and locks. Successful completion has its own `released`
flag, separate from immediate revocation. The store's revocation flag is visible
to callback threads. The existing disposition close path uses the same extracted
revoke/drain operation; its independent retained-owner behavior is preserved.

Two additional TCP regressions start an external drain, observe actual socket
cancellation, and then reenter store close from the still-running callback. The
callback must report incomplete drain without blocking on a store monitor held
by the external closer; the external close completes after the callback is
released. Transport timeouts and resource bounds are unchanged. This is not a
general concurrency guarantee for all store mutation APIs.

## Evidence and boundaries

```bash
python3 -m scripts.v53.pending_drain_evidence RAW --store
python3 -m scripts.v53.store_drain_negatives RAW
```

The explicit store scope requires all original parent and retained storage to
survive the failed-close interval, only release operations during retry, and zero
accounting at successful store return. Three original lock identities must remain
held across failure and become available after successful close. Original path,
inode-key, file-hash and complete accounting observations are checked separately.
The underlying authority remains a conditional fixture; lock probes run in real
separate JVMs but do not turn this into a native membership or crash history.

The original-first negative driver combines twelve accounting/call mutations
with six lock-observation mutations. A different lock inode, missing scope,
premature unlock or retained lock after success cannot qualify even when files
and final counters look correct. The older retained-owner scope still requires
restoration to its pre-retention baseline; it cannot substitute for store closure,
which must release that baseline too.

Normal failed-force/store cleanup and linked-INTENT voter handoff are also checked.
This batch does not qualify every failed constructor, replacement/recovery guard
using a revoked-owner predicate, or arbitrary filesystem-close failure. Native
joining and required-four custody, remaining export/task/control lifetimes,
combined maxima/headroom and final-source hosted qualification remain open.
The frozen 544 Phase 3 hosted histories and later-phase 3310-case plan are unchanged.
