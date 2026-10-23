# Pending context under the actual local owner

Status: private retention/withdrawal locally qualified. Phase 2 remains **OPEN**;
transferred generation/source lifetime is not enabled by this batch.

`MembershipGrantJournal.openContextual` is an opt-in private owner. It admits the
two [context files](PHASE_2_PENDING_CONTEXT_FILES.md) in its allocator inventory,
uses the existing exclusive replica lock and shared JOURNAL reservation, and
charges active/candidate metadata together with grants, pending vote completion
and application metadata. The ordinary `openApplying` path still rejects these
extra files rather than silently ignoring their ownership.

## Exact retention

`retainPendingContext` accepts no caller-selected original files or backing source.
It requires an actual carried pending vote, its complete inactive original
generation, a newer installed selection of that exact entry, the corresponding
local PROMISE/BASIS, and the actual retained source. No incomplete capture,
selection, vote, floor, retirement, rotation or application staging may overlap.

The owner derives the expected context from those exact bytes. An existing active
context must already equal it; a candidate may only be its exact prefix. Combined
JOURNAL completion space is checked before writing. Under identity/hash guards,
it re-forces each backing source member and both source directories, then writes
and forces the bounded context candidate, atomically publishes it and forces the
owner directory before return.

Reopen reserves and validates actual source files first, then checks and resumes
the same context request. Corrupt active authority cannot be repaired from a good
candidate. This recovery may retain already-owned evidence after a higher volatile
ballot is observed: it grants no ballot, emits no old application/vote ACK and
does not lower that observation.

## Pins and withdrawal

At this entry point, the complete original generation, source and pending vote
must all remain. An active or pending context blocks new authority-changing work.
The context cannot yet replace those original physical owners or authorize their
deletion. A context-aware open still refuses a missing original generation.

`discardRedundantPendingContext` provides a safe return to the existing path. It
first completes/reseals the exact context request and revalidates its complete
original generation, vote and source under the lock. Only that redundant context
file is deleted, followed by a parent-directory force. A pending replacement must
finish first. A lost cleanup return is idempotent; absence of the context creates
no new authority. Interrupted deletion tests reopen and reaccept the original
entry under the already installed newer ballot with all required originals intact.

## Qualification

The focused reactor passes **59 Java tests**, including seven owner tests and the
existing context codec/files, staged-application and compatibility boundary suites.
Owner tests cover force-before-context order, exclusive lock, source inode
substitution, combined budget refusal before writes, corrupt active input,
ordinary-owner refusal, missing original generation, higher observed ballot,
blocked authority mutation and redundant withdrawal with interrupted cleanup.

Twelve actual owner boundaries are each interrupted twice with injected
`IOException`, closed, reopened and completed. Evidence retains initial,
interrupted, second-interrupted and final physical directories plus observed force
events. The independent Python replay checks unchanged protected bytes and
directories, exact context reconstruction from the real local source/journal,
candidate prefixes, force order and absence of old ACKs. It rejects **12 exact-reason
mutations**, validates relocated evidence, and agrees under normal and optimized
Python. See the [source/build/raw index](phase2-evidence/journal-context.json).

These owner interruptions are **not fresh-process crashes**. The existing context
file component's 32-case/96-JVM halt/SIGKILL qualification remains separate. The
owner evidence does not establish power-loss behavior, remote ownership or
independent application-image semantics. Its historical bootstrap is conditional.

```bash
/opt/maven/bin/mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -pl :general-search-engine-replication -am \
  '-Dtest=V53JournalContextTest,V53PendingContextTest,V53PendingContextFilesTest,V53StagedApplicationTest,V53SourcePacketTest,V53DeclarationsTest,V51VersionBoundaryTest' \
  -Dsurefire.failIfNoSpecifiedTests=false package
# Use the v53JournalContextEvidence directory printed by the test.
python3 -m scripts.v53.journal_context_evidence <owner-evidence-directory>
python3 -O -m scripts.v53.journal_context_evidence <owner-evidence-directory>
```

## Next complete transition

Load/reconstruct detached original authority separately from live source/journal
maps, then connect exact generation/floor/source maintenance and
[protected capture/rebinding](PHASE_2_PENDING_TRANSFER.md). Preserve old
certificate bytes through a replacement ACCEPT and subsequent publication/floor;
demonstrate repeated higher observations across three/four/five and joint voters
within all physical reservations. The active-context guard cannot simply be
removed. Maximal valid unions that exceed the existing source limit require a
completion/admission design, not a claim that a capacity refusal resolves liveness.

Offline initialization and the full Phase 2 physical closure audit remain pending.
No public runtime, protected CI or paid cloud is enabled here.
