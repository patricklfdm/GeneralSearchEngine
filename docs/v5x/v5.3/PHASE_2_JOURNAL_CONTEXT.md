# Pending context under the actual local owner

Status: private retention/withdrawal and exact first governing-floor retirement
are locally qualified. Phase 2 remains **OPEN**; later campaign/source turnover
and complete transferred lifetime remain pending.

`MembershipGrantJournal.openContextual` is an opt-in private owner. It admits the
two [context files](PHASE_2_PENDING_CONTEXT_FILES.md) in its allocator inventory,
uses the existing exclusive replica lock and shared JOURNAL reservation, and
charges active/candidate metadata together with grants, pending vote completion
and application metadata. The ordinary `openApplying` path still rejects these
extra files rather than silently ignoring their ownership.

## Exact retention

`retainPendingContext` accepts no caller-selected original files or backing source.
Initial creation requires an actual carried pending vote, its complete inactive original
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

An active or pending context blocks general authority-changing work. The narrow
maintenance methods described below may retire the original generation under an
exact governing floor. Source, pending vote, context and that floor remain pinned.
A context-aware open refuses a missing original generation without this complete
floor; it never silently rebuilds a missing source or changes a vote.

`discardRedundantPendingContext` provides a safe return to the existing path. It
first completes/reseals the exact context request and revalidates its complete
original generation, vote and source under the lock. Only that redundant context
file is deleted, followed by a parent-directory force. A pending replacement must
finish first. A lost cleanup return is idempotent; absence of the context creates
no new authority. Interrupted deletion tests reopen and reaccept the original
entry under the already installed newer ballot with all required originals intact.

## Qualification

The original retention batch's focused reactor passed **59 Java tests**, including seven owner tests and the
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

## First generation retirement under an exact context

`contextFloorCopy`, `establishContextFloor` and `retireContextOriginal` are private,
separate maintenance entries. They validate the already forced context against
the actual original local source, pending vote and unchanged installed selection.
They reuse the governing-quorum copy and retirement implementations; no recovered
context is converted into a new generation `Owned` receipt. Floor copies come from
the actual selected generations. Empty replay/end reservations are released before
reserving complete floor copies, within the existing seven-image bound.

For a complete active context, reopen defers old-vote verification until the real
source, floor and retirement owners have been opened. The context reconstructs
the exact old selected materialization and vote, including its original certificate.
An intact physical old generation must still match every original byte. Partial
deletion requires the exact retained retirement inventory and governing floor.
After the old directory is gone, that complete floor must still bind the current
local generation and original parent. Missing/corrupt context, source, floor or
vote is refused without recreating authority. A partial context candidate alone
never enables deferred old-generation verification.

The [retained local evidence index](phase2-evidence/context-retirement.json) records
67 passing Java tests, including four new methods. It covers a real three-owner setup, exact clean retirement/reopen, all 25 existing retirement
boundaries followed by a second interruption during context reseal, and six partial
floor boundaries. Tests keep original source/vote/context bytes unchanged and reject
ordinary source/floor/journal/campaign mutations. Independent replay reconstructs
the original context and both exact floor copies before deriving the only deleted
generation; twelve exact-reason negatives and portable normal/optimized replay
remain required. Typed application semantics and resource leases are Java checks.

This is a first three-voter transition, using injected IOException. Four/five-voter
context lifetime, fresh-process repeated recovery and a subsequent campaign are
not established by it. The existing separate four/five-voter retirement tests
continue to test their own profiles. No limit, public factory or frozen format changes.

```bash
python3 -m scripts.v53.context_retirement_evidence <v53ContextRetirementEvidence-directory>
python3 -O -m scripts.v53.context_retirement_evidence <v53ContextRetirementEvidence-directory>
```

## Next complete transition

The first original-generation retirement now loads/reconstructs detached original
authority before pending-vote recovery. Next connect later source/floor lifetime and
[protected capture/rebinding](PHASE_2_PENDING_TRANSFER.md). Preserve old
certificate bytes through a replacement ACCEPT and subsequent publication/floor;
demonstrate repeated higher observations across three/four/five and joint voters
within all physical reservations. The active-context guard cannot simply be
removed. Maximal valid unions that exceed the existing source limit require a
completion/admission design, not a claim that a capacity refusal resolves liveness.

Offline initialization and the full Phase 2 physical closure audit remain pending.
No public runtime, protected CI or paid cloud is enabled here.
