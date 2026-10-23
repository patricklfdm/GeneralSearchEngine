# Same-round durable next-slot storage

Status: private storage integration. Phase 2 remains **OPEN**. This admits the
[bounded round proof](PHASE_2_ROUND_COVERAGE.md) to actual storage; it does not
restore READY after restart or enable the public membership runtime.

## Original authority and publication

The generation reader accepts legacy first-slot coverage unchanged and verifies
the new round format with its original PROMISE/SELECTED. Later votes require the
exact current published predecessor, the original selected ballot and a new entry
originating in that ballot. The selected carried choice applies to the first slot;
it cannot be reused as the required entry for every later slot. Only one pending
slot is permitted, and higher observed/promised ballots still fence the owner.

Application preserves the original first parent/end alongside selected-source,
current-parent and retained floor/BASIS endpoints. Before a new ACCEPT, admission
sizes the round coverage with those endpoints under the unchanged 4 KiB ceiling,
and retains existing packet, ancestry, journal and image completion reservations.
Oversized metadata is not made admissible by dropping original proof or increasing
limits.

Publication retains exact original first and current ENTRY/payload/ACCEPT/PROOF/
CERTIFICATE objects, with authenticated ancestry. Intermediate ordinary proofs
are omitted from the next compacted generation. Repeated publication reconstructs
the exact already-installed manifest; it cannot substitute a different original
receipt. Covered-vote retirement validates the old generation's own coverage
before deleting only its exact application staging and pending vote.

The storage reader verifies original selected-source frames independently of the
round metadata. Duplicate PREPARE still returns its original frozen BASIS/source;
a fresh ballot captures the advanced prefix and any current unresolved vote.
An old installation request cannot roll an advanced generation back. Stable-round
continuation stops at a membership boundary; activation in a new authority is
fresh-campaign work.

## Local qualification

The source/build/log inventory is recorded in
[the local index](phase2-evidence/round-storage.json).

The three new Java methods exercise three actual local owners:

- One original ballot through thirteen published slots: initial DATA, then twelve
  alternating BARRIER/DATA successors. Every phase reopens the owner, every
  completed publication is retried before and after governing-floor maintenance,
  and original BASIS/SELECTED/source bytes remain unchanged. Each settled node has
  one generation, one source and two physical image files. The small fixture
  retains at most 25 source objects and two ancestry groups.
- Wrong next index, previous entry and origin, a higher ballot, conflicting
  acceptance and missing first phased observations reject. A fresh PREPARE
  preserves the actual advanced prefix and pending tail.
- Subsequent publication is interrupted at manifest force, selector publication,
  end deletion and covered-vote prefix write; recovery is interrupted again and
  must complete the exact original result. These are injected I/O failures in the
  same JVM, not halt/SIGKILL evidence.

The Python replay derives each generation from the retained original three-node
votes and applied ends, including exact catalogs, first/current phased objects,
checkpoint/ancestor statements, ACKs, source packets, manifests and selectors.
It checks 39 published node snapshots, original decision continuity, safe final
retirement and the subsequent fresh capture. Original evidence is validated before
any negative mutation; relocation and Python optimized-mode replay are separate
checks. It does not infer force ordering from final files or independently verify
core image semantics.

The initial development logs remain retained. They record a test-driver accessor
name error and an incorrect new object-count assertion that omitted retained proof
objects. No production capacity was raised to satisfy that assertion.

## Remaining work

- [Same-round process recovery](PHASE_2_ROUND_PROCESS.md) now adds 22 halt/SIGKILL
  cases through the third slot, repeated interruption and exact physical replay.
  Other cross-view and maximal lifetime histories remain open.
- [Actual carried-first-entry publication](PHASE_2_CARRIED_PUBLICATION.md) now
  connects earlier original votes to new-ballot installation, maintenance and
  continuation. Its dedicated process-crash qualification, membership boundaries,
  maximal payload/metadata headroom and cross-view lifetime remain open.
- Complete bootstrap, torn PROMISE recovery and the rest of the
  [storage closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).

Conditional historical bootstrap, local passes and immutable original receipts
are not public runtime, distributed activation, protected CI or cloud evidence.
