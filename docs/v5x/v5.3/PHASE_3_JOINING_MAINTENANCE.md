# Reconcile a joining voter from the forced governing floor

Phase 3 remains **OPEN**. After native JOINT publication, the old owner can still
have its preceding configuration's peer-retention ledger. Previously,
`publishedMaintenance` tried to reconcile it with an empty joining-copy list
before allowing the read-only maintenance download. That refused ADD/REPLACE
before maintenance could acquire the actual joining generation it required.

The published-maintenance permit now retains the original generation,
PROMISE/SELECTED and observed-ballot fences without making that premature ledger
change. It still refuses pending votes, lost ownership and higher observed
ballots. Grant creation keeps its existing configuration guard; this change
alone cannot make a new grant or infer that a configured identity is installed.

Maintenance computes the missing joining identity from the validated current
history and old ledger, prioritizes its complete prefix/generation download,
and requires both governing majorities **and** that joining copy. STATUS hints,
application acknowledgements, publication acknowledgements, and an old-only
quorum without the joining copy do not satisfy the new condition. Exact current
cut, permanent identity, original receive provenance and existing bounded
transport/deadline checks still apply. Missing/unavailable joining copies fail
before forcing a floor or changing the ledger.

Only after the complete governing floor forces may the owner reconcile its
ledger. It reads the actual retained floor originals, matches its local floor
generation to the current native generation, and supplies only the newly added
member's complete copy to the existing reconciliation verifier. Old peers keep
all existing uncertainty; removed identities leave only after stable FINAL.
Only the separate existing complete-copy observation step may then narrow old
endpoints. Repeating an unchanged reconciliation does not write a new revision.
The floor retains recovery authority across a crash before ledger completion;
partial/releasing/stale floors cannot supply this permission.

The ordering checks cover all seven legal transition profiles and every local
participant. With all requested members available, at most three remote members
are needed for the quorum plus joining-copy condition. Each remote prefix owns
one SOURCE, while generation metadata uses CONTROL reservations. This is a
conditional ordering bound, not maximum combined storage qualification; all
original sources, images, floors and incoming requests must still fit their
unchanged limits at runtime.

The whole native check extends the actual old-two-of-three joining history:
independent JVMs probe all three old replica locks after snapshots; the actual
new journal supplies its complete current copy; reconciliation refuses before
the floor and preserves all old peer/learner obligations after it. Focused
configuration/copy checks and existing pending-vote/higher-ballot regressions
are recorded separately from that full native result in the
[source-bound component receipt](phase3-evidence/joining-maintenance.json).
The native case passed in 715.321 seconds. It supplies the three complete
copies explicitly from their still-open journals; autonomous TCP maintenance
acquisition is not claimed. Its retained events place the final forced floor
return before the peer-ledger parent force, and both original learner ledgers
still contain endpoint 5 and renewal debt 3.

This component does **not** initialize a new joining journal's own retention
ledgers. `openJoined` can already own the native counter/grants, but ordinary
peer/future/learner initialization intentionally accepts only unused genesis.
Before a complete joint campaign, a separate original joining transaction must
safely seed the new owner from authenticated retention obligations. Do not
reconstruct a supposedly empty ledger from a later selector or bypass the
configuration guard. Joint FINAL/stable barrier, autonomous continuation,
independent physical/history replay and all-profile/process acceptance remain
in the [deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md).

Rollback restores the earlier safe refusal before maintenance acquisition.
Preserve any already forced floor and reconciled ledger originals; there is no
new durable format or resource allowance to migrate or erase.
