# Process recovery of exact pinned-source retirement

Phase 2 remains **OPEN**. This batch qualifies the new
[pinned BASIS image retirement](PHASE_2_RETIREMENT_SOURCE_IMAGES.md) on its own
force and deletion boundaries. Earlier covered-vote and floor-image process
receipts describe different transactions and do not substitute for this gate.

The seed uses actual public four-voter EMPTY bootstrap, an original minority vote,
the disjoint majority's typed publication, a later all-voter selection and three
actual complete governing-floor copies. Every case restores the same original
admitted node path. A worker opens that admitted owner and retires the inactive
generation using the retained floor; it does not fabricate peer ownership or
replace the original source with an equivalent image.

Thirty-two boundaries cover retained metadata, exact image binding (including a
partial write), original source resealing, floor resealing, deletion authority,
original/saved deletion and final cleanup. Both process halt and external SIGKILL
run at every boundary. A second fresh worker stops again at authority resealing
when authority remains, or during forced owner opening otherwise. A third fresh
worker completes the same transaction and checks duplicate completion. This is
64 cases and 192 workload workers, with 32 additional cross-process lock probes.

Before SIGKILL, a separate process must fail to obtain the owner's actual
`replica.lock`. Its canonical stdout, stderr and exit result are retained along
with each workload worker's trace, exit code, requested boundary and mode. This
tests continuous lock ownership at the observed cut. It is not a power-loss or
filesystem durability simulation.

The independent reader starts from original bootstrap and voting/publication
bytes, derives the exact local floor and source binding, then checks both
interrupted snapshots and the final snapshot byte for byte. It verifies source
and floor force order before deletion, the kill handshake, exact exit records,
admitted paths, observations and typed scope fields. Original source, active
generation and floor bytes must remain unchanged. Physical inventories stay
within seven images and six sources, and workers check shared reservations at
callbacks and zero retained leases on normal close.

Twenty-four negative evidence variants target originals, floor, binding/backing,
premature deletion, force order, exit/lock results and false success/scope.
Unmodified evidence must pass before any negative can count. Normal, optimized
Python and relocated replay must agree. Executed results and source/build/class
inventories are recorded in the
[local evidence index](phase2-evidence/retirement-source-process.json).

The fixture uses small actual application images. This establishes neither
maximum byte headroom nor all profiles under every process schedule. Complete
cross-view lifetime, proof/context-bearing covered recovery, maximal resource
acceptance and the Phase 2 closure audit remain outstanding. Production Java,
frozen formats, limits, POMs, workflows and public runtime are unchanged by this
qualification batch; no V5.2 experiment or cloud operation is involved.
