# Native allocator and journal ownership after joining

Phase 3 remains **OPEN**. `MembershipGrantJournal.openJoined` now consumes the
actual completed [original retirement](PHASE_3_JOINED_RETIREMENT.md), transferring
exclusive filesystem ownership and surviving reservations into the existing
native allocator, current-generation reader and grant journal. Local counter
allocation and PROMISE/BASIS creation use their normal durable implementation.
This component does not expose the joining member as a ready public runtime.

## Forced decision and exclusive custody

Before writing, validate the complete original installed history, derive the
surviving inventory from the original deletion plan and preflight an entire
quiescent storage replacement. Force `native.json` in its fixed private sibling
directory, binding the original retirement decision/completion fingerprints,
plan/root/identity, local path, directory and record inodes and target native
reservations. Force the directory and parent before transferring ownership.

The actual root and every retained sidecar lock move without a descriptor
close/reopen. Any live nonempty receiving descriptors whose payloads were
retired also transfer until the new owner closes. Old custody, retirement and
lease handles are revoked; their later close cannot release the successor's
locks or charges. Transfer has no user callback between replacing accounting
and moving descriptors. Partial transfer failure closes all acquired handles;
it cannot leave a usable partially transferred owner.

Complete replacement rechecks the exact original leases/categories/extents and
absence of pending work under the resource monitor. It validates all proposed
counts, metadata, staging and protected completion headroom under the existing
limits, then replaces the whole group atomically. Initial current-generation
and source readers must claim each exact issued lease once. The surviving
native group contains the normal JOURNAL reservation, MISC reservation, one
GENERATION's actual metadata and each actual APPLICATION image. Later native
generations and sources use ordinary reservations.

The 64 KiB decision is reserved before initial staging, bringing fixed private
companions to 960 KiB within the same GENERATION limit. Immutable surviving
proofs and root metadata must fit the existing 2 MiB MISC reservation after
handoff. Original cold-retirement accounting conservatively includes the new
companion even before transfer. Public format catalogs, resource ceilings and
timeouts are unchanged.

## Mutable native recovery and joining provenance

`reopenJoined` requires the exact complete original handoff, actual original
root and sidecar locks, and all retained joining, placement, retirement and
typed configuration proofs. Missing, torn, copied or altered records refuse;
the cold entry never reconstructs admission from caller arguments. A complete
original handoff forced before transfer can be reopened after the old process
has closed. A live retry may re-force a complete exact handoff. Recovery of an
incomplete handoff record is not implemented by this entry.

Immutable enrollment proof checking is separate from installed-generation
inspection. It returns no ownership or stored-history token. The allocator
checks this proof owner instead of requiring initial-bootstrap receipts; the
joining identity is never inserted into ROOT/GENESIS initial membership.
Bootstrap entry points retain their original admission requirements.

Mutable counters, pending counter recovery, grants, source captures, selectors
and generations are read through their existing native owners and private
stored-history capability. Each loaded current history must preserve the exact
original typed receipt and certified INTENT bytes and may not precede the
original installed cut. Incoming adoption checks this binding before mutation.
The generalized enrollment check permits that original catalog row to survive
later views, while initial joining still requires the precise immediate JOINT
or completed target view. This separation does not establish later-view quorum
qualification by itself.

## Evidence and remaining work

The [component receipt](phase3-evidence/joined-native.json) records immutable
source snapshots, actual targeted executions and retained development failures.
Coverage includes live descriptor/charge handoff and stale closes, genuine
counter and grant persistence, cold grant replay, original cold-retirement
handoff, pre/post-transfer interruption, missing/torn/copied proofs, live proof
mutation before another write, interrupted counter nonreuse and bootstrap
admission regression. Independent JVM probes check actual root exclusion.

Historical membership proofs in the joining fixtures remain conditional.
Native local operations here do not establish autonomous joint-majority
activation, all-profile history replay, full halt/SIGKILL qualification or
public typed materialization. Minimum old-quorum INTENT delivery, joined
retention, joint FINAL/fresh barrier and those full qualification gates remain
in [deferred acceptance](PHASE_3_DEFERRED_ACCEPTANCE.md). Expensive complete
measurements remain deferred to the planned hosted parallel runs.
