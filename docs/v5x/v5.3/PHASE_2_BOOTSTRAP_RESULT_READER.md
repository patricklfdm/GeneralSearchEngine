# Phase 2: immutable bootstrap result after local progress

Status: private reader locally qualified; Phase 2 remains **OPEN**.

`MembershipBootstrapCoordinator.readResult` reads the original committed result
through a separate immutable-authority path. It exclusively owns the operation
lock and validates the original plan/image, exact four-decision journal, receipt,
all local ROOT/GENESIS/NODE records, preparation, compact admission and seal.
Original operation/target parent bindings, directories, file identities and bytes
are rechecked before return. Pending or missing local seals are refused.

It does **not** require unchanged runtime counters, grant journals, generations,
or absent derived core directories. The original source and planning projection
are no longer dependencies after the committed transaction. It neither reads nor
repairs mutable runtime authority. Node lock files are stat-checked only: opening
and closing a second descriptor could release a live POSIX owner's lock, so this
reader never opens `replica.lock` at all. It performs no force, rename or deletion.

## Qualification

Five Java methods cover six actual typed-coordinator size/source profiles and 24
initial voters, with real counter/grant/reopen progression and preserved derived
core markers. Result reads run while every node is owned; 48 external JVM lock
probes confirm exclusion survives those reads. The completed output remains byte
identical before/after a result read. An owned operation also remains protected
after a rejected duplicate read.

Missing/torn original records, a foreign receipt, linked metadata, pending seals,
operation inventory changes, same-byte inode substitution during a read and a
non-directory core are rejected. A missing mutable allocator deliberately does
not erase historical commit evidence: result reading succeeds, but the separate
admitted store opener fails without recreating it. This separation is tested.

The independent replay derives initial and progressed authority, actual grants,
source copies and the result from the original plan/image. Seventeen negatives
include a result substituted with the current counter or a foreign receipt hash.
The existing store replay remains available with its original receipt profile.
Normal/optimized Python and relocated copies must agree. The
[evidence index](phase2-evidence/bootstrap-result-reader.json) records actual
outcomes and artifact/source provenance.

## Remaining work

- `readInitialResult` remains the stricter original-layout diagnostic.
- This new reader does not make transaction resume tolerant of progressed nodes.
  Finishing other local seals after one sealed node progresses still needs its
  own bounded recovery path, preserving completed immutable originals and all
  mutable state. Never restore a runtime counter or log from a bootstrap payload.
- Public offline entry, typed coordinator process deaths, transferred context
  lifetime, maximal/cross-view qualification and the Phase 2 closure audit remain
  pending. The reader does not assert runtime health, voting readiness, typed
  image semantics independently, power-loss durability or remote force.
- Local-only development; no legacy format, public runtime, cloud, workflow,
  POM, resource catalog or frozen fixture change.
