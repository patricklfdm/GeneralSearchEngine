# Phase 3 — original allocator and promise force audit

The [continuous learner reader](PHASE_3_SAME_VIEW_LEARNER.md) composes original
storage, transport, exports, maintenance and all three retention ledgers. It is
still a partial whole-history qualification. Auditing actual reader predicates
found that old-voter allocator bytes were derived and compared, but their write,
force, rename and directory-force callbacks were not bound to each local grant.

On a disposable copy of the retained `3-REPLACE` original, deleting node 1's
first `ALLOCATOR_FORCED` callback still passed that complete reader. The raw
original is unchanged. This demonstrates a validator coverage gap, not a failed
production force. The historical receipts remain accurate for their stated scope.

## Continuous ballot derivation

`scripts.v53.joining_same_view_ballot` validates the entire untouched prerequisite
chain before checking the new boundary. Bootstrap counters and promises come
from independently derived original bootstrap inventories. The joining owner's
adopted initial counter comes from the original JOINT certificate, compared with
its placed allocator; placement is not treated as a ballot reservation.

Every observed reservation has exactly seven owned callbacks: before-write,
created, written, forced, renamed, directory-forced and before-return. A local
grant requires one complete reservation after the previous original capture and
current-generation force, and before capture begins. Remote grants cannot create
a local reservation. All original grants bind promise write/force occurrences;
the newer-authority adoption's fence is derived from its original certificate.
No extra allocation or promise force may remain unbound.

Each reservation derives `max(previous counter, observed promise) + 1`. An
unused reservation after the original retaining reopen is explicitly burned;
it cannot be relabelled as a grant or moved to a different owner lifetime. The
later adoption fence raises the next allocation even though it is not a local
grant. Captures, applied/published snapshots, installed generations and cold
storage must equal the continuous counter. The native snapshot is compared at
its actual post-burn boundary, not at the earlier initialization that reused the
same immutable ledgers but had a different counter.

The original contains eleven reservations, ten self-grants, one unused
reservation and twenty forced promises. Eighty-seven allocator comparisons end
at counters 9, 1, 1 and 9 for nodes 1–4. The reader does not reset its expected
counter from an observed final snapshot.

## Qualification

```bash
python3 -B -m scripts.v53.joining_same_view_ballot /original/raw \
  --qualify --workers 4
```

Nineteen mutations affect only allocator/promise callbacks on independent
disposable copies. They cover omitted/reordered forces, duplicate/incomplete or
unowned writes, grant/open boundaries, the unused reservation and unbound promise
writes. All physical files, wire records, directories and other observations
must remain identical; each focused rejection requires its exact named reason.
Mutated upstream prerequisites are not rerun. The full unmodified prerequisite
must pass first, and the receipt declares the narrower negative scope.

The [batch receipt](phase3-evidence/same-view-ballot.json) records the original
input, reader source, tests, actual execution and portable replay. Failed
development attempts and the original coverage-gap reproduction are retained.

The frozen reader passed all 533 joining Python tests, including 17 focused
allocator tests. Full original-first qualification and nineteen exact negatives
passed in 86.264 seconds. A 20,001,588-byte archive retains the original, frozen
reader, audit mutations and diagnostics: 8,696 files and 1,206 directories were
verified after extraction. The extracted reader replayed with `-O -B` in 52.797
seconds, producing the exact same result with unchanged source/input inventories.

## Whole-history coverage remains open

This gate qualifies allocator/promise causality for this one healthy REPLACE.
It does not infer full coverage from event counts or from an event name appearing
in a reader. A second disposable-copy audit deleted the first node 1
`INSTALL_IMAGE_FORCED` callback; the prior complete reader also accepted that
copy. Remote installation ACKs and the joining proposer's final recovery are
already checked, but ordinary proposer-local installation forces need the same
complete binding. This second reproduced gap remains a separate next task.
Other callback families and their authority intervals still need explicit audit.
Current-source profiles including REMOVE, whole-history fault/process cuts and
frozen acceptance mapping remain required. All full physical/network/process
and Phase 3 completion flags stay false.

No Java, POM, workflow, production bounds or cloud experiment changes.
