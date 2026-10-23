# Phase 2: admitted initial-voter store

Status: locally qualified private entry; Phase 2 remains **OPEN**.

`MembershipGrantJournal.openBootstrapped` composes the existing contextual owner
with immutable initial-voter admission. It requires the exact original preparation,
seal and compact admission, bound to ROOT/GENESIS, local identity and both local
paths. Validation runs under the existing `replica.lock` **before allocator
recovery can force or rename an unreturned reservation**. A missing seal, malformed
or foreign record, candidate-only seal, wrong path or identity, linked member, or
old component-only layout is refused. No bootstrap file is recreated by opening.

The allocator retains the three immutable records' bytes and inode identities and
checks them before later writes. Duplicate opens still use the process-local owner
registry before opening another POSIX lock descriptor. The expected core parent
binding is guarded; a legitimate derived core directory may exist after startup.
The entry does not interpret its contents as bootstrap authority or reset them.

The same full contextual GrantJournal opens sources, generations, floor/retirement,
rotation, pending vote/context and application components. Existing component
entries keep their inventories. The complete entry uses the existing **one MISC
reservation**, without changing the catalog, capacities or legacy 1.1/1.2 paths.
This does not by itself prove the complete maximal miscellaneous lifetime bound.

## Validation

Six new Java methods cover all six size/source combinations (24 initial voters),
real counter reservations and fresh grants, duplicate grant after reopen, original
receipt preservation, lost/torn/corrupt/foreign/rehashed admission before pending
counter recovery, interruption during recovery again, same-byte inode replacement,
links, path/identity mismatches, exclusive ownership and lease cleanup after failed
staging reservation. A derived core marker survives reopen unchanged.

The independent Python replay first derives the complete initial inventory from
the retained original plan/image. It then validates actual PROMISE/BASIS records,
source copies, counters, required force/return order and exact final inventories.
Only the fresh UUID BASIS identity is observational; its context and dependent
bytes are independently bound. Fifteen mutations must fail for exact reasons;
normal/optimized Python and a relocated copy give equal results.

The related allocator, ownership, admission-data and context regression suites are
included. The first run exposed an old context test that still expected the message
from before the process-local ownership registry. Its rejection was correct; the
assertion now checks `STORAGE_FAILURE` and the registry's exact diagnostic. The
failed log is retained. Production ownership code is unchanged in this batch.

The [evidence index](phase2-evidence/bootstrap-store-admission.json) records the
actual outcomes, raw inventory, compilation inputs, producer classes and artifacts.

## Limits and next work

- Initial voters in immutable ROOT.initial only; no later learner admission.
- The producer uses the admitted transaction with no-op typed callbacks. Complete
  typed coordinator coupling and its process qualification remain pending.
- No public runtime/API activation, network vote, power-loss or independent typed
  image-semantic claim. A primitive core marker only tests preservation/path shape.
- Coordinator result/resume must tolerate legitimate progress of already sealed
  targets while preserving exact originals; it must never restore initial mutable
  files. Current initial-state transaction inspection is not that implementation.
- Transferred context lifetime, maximal capacity and the complete Phase 2 physical
  audit remain open. All work stays local; no workflow, cloud, POM or frozen hash
  change accompanies this batch.
