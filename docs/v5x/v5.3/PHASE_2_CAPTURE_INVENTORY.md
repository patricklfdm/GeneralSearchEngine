# Deferred capture inventory admission

Phase 2 remains **OPEN**. This component removes one constructor-order obstacle
to protected context capture: a pending source's exact content may depend on a
different, complete retained source. It does not yet enable context PREPARE or
persist/recover a context rebind.

## Storage behavior

`MembershipBasisSources` can admit a pending capture in two steps. It first
validates and reserves the complete retained sources. A scoped, read-only lookup
then exposes only exact BASIS-bound packet/image bytes to a resolver. Partial
pending sources cannot be used as original authority; changed BASIS metadata is
rejected. The lookup expires when the callback returns or throws. It creates no
`Owned` observation and performs no force, suffix completion or grant return.

The resolver's result must retain the original pending PROMISE, exact completed
BASIS if present, packet binding and image inventory. The constructor validates
any incomplete source against that exact request and reserves its full eventual
size. It rechecks the entire inventory, including original inodes, before the
existing source sealing loop. Failure releases only constructor-owned leases;
caller-held reservations and stored bytes are preserved. Existing fixed-plan
callers delegate to this path without changing their wire/disk formats, force
order, or frozen resource counts.

`MembershipCaptureFiles.plan` additionally accepts an explicit verified image
inventory. This preserves the union required by protected original/current
captures instead of always retaining only current-generation images. The old
entry point still supplies current images. The new overload verifies packet/image
binding and clones caller arrays.

## Local qualification

Nine new Java tests exercise 3/4/5-voter inventories at empty-intent, partial
packet, partial image and complete-BASIS boundaries; scoped lookups; corrupted or
unbound originals; changed pending prefixes; substituted resolver results; capacity
failure; inode replacement during resolution; and an explicit two-image capture.
Those inventories originate in actual earlier local PREPARE/capture operations.
The deferred constructor leaves bytes unchanged. The existing journal recovery
subsequently completes the same request. Historical generation and quorum inputs
remain conditional fixtures, not a complete bootstrap/runtime qualification.

The independent Python replay validates each original generation/source first,
derives the exact pending intent, prefix state and completed journal/source, and
checks that inventory admission changed no bytes. It covers 12 retained cases,
ten exact-reason mutations, portable relocation and Python optimized mode. It does
not infer force ordering from unchanged snapshots or independently replay all
temporary refusal cases from the Java tests.

Focused existing source/capture, torn-BASIS and context recovery regressions run
alongside the new tests. Build/raw hashes and exact counts are retained in the
[evidence index](phase2-evidence/capture-inventory.json). The first failed run is
retained: the new test initially called a kind-specific decoder with a null kind;
fixing that fixture parser did not change production behavior.

## Next integration

Protected context reconstruction must consume these read-only originals without
inventing a force/ownership observation. The actual transaction must reserve
completion capacity before PROMISE, retain capture intent through forced source,
BASIS and context replacement, and recover the same original after interruption.
Only explicit exact completion may return a grant. Repeated backing retirement,
selected-generation slot reuse, floor replacement and maximal lifetime accounting
remain in the [closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
