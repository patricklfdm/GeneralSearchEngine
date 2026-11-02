# Phase 3 — original SELECTED journal ownership

After the [installation write correction](PHASE_3_SELECTED_INSTALL_WRITES.md),
removing node 1's first `SELECTED_WRITTEN` from the retained REPLACE original
still passed the complete prior composed reader. The audit retains the changed
copy and its result. This establishes a reader omission; original stored SELECTED
bytes, wire traffic and native execution are unchanged.

## Complete append and original authority

`MembershipGrantJournal.selectCurrent` calls `append` and then returns the fixed
selection. Its ordinary new append has exactly four callbacks:
`SELECTED_BEFORE_WRITE`, `SELECTED_WRITTEN`, `SELECTED_FORCED`, and
`SELECTED_BEFORE_RETURN`. There is no SELECTED prefix-write callback. An already
fixed selection returns without another append; a duplicate reply cannot invent
another four-event transaction.

The shared `selection_journal_evidence` reader checks this complete sequence for
every selected owner in the entire original event stream. Transactions may
interleave across nodes, but a node cannot borrow another owner's scope, write,
force or return. Every row has its exact original shape. Every complete append
matches exactly one original force occurrence and one `(node, selection digest)`
binding; no transaction or binding may remain unused or be counted twice.
Incomplete, reordered, duplicate, unknown or unbound journal callbacks fail.

The caller still derives SELECTED bytes, source eligibility, ballots, installed
snapshots and original wire exchanges independently. It now supplies the complete
append's original causal bounds, rather than checking only the force position:

- A proposer starts writing after all selected original grants and their required
  PROMISE deliveries, and finishes before its first SELECTED send.
- A remote selected voter starts after its actual SELECTED request is received
  and finishes before its actual installation response is offered. The existing
  installation sequence also requires return before installation begins.
- The final same-view proposer has the same journal rule; its installation keeps
  its separate delivered-ACK and cold-reopen boundary.

ADD/REPLACE, both REMOVE profiles and the continuous REMOVE process reader use
the shared rule. The two exact `SELECTED_RETENTION_COMPLETED` and
`SELECTED_LEARNER_RETENTION_COMPLETED` names belong to the separate continuous
retention readers and are not journal appends. Other SELECTED-prefixed callbacks
cannot silently escape ownership checks.

## Qualification scope

Five consumer regressions cover ordinary proposer, remote voter, final recovery,
REMOVE proposer and REMOVE remote paths. They prove 45 negative subcases were
accepted by the previous reader, including writes placed before authority while
the later force and final bytes remain valid. Seven additional reader regressions
cover interleaving, every append boundary, exact shape, binding reuse, orphan
transactions, the explicitly separate retention callbacks and raw/normalized
transport mutation boundaries. Fixture observations
list the native sequence explicitly and preserve causal indices when moved.

The original-first network qualification adds 23 exact negatives: seven variants
for each of the three roles and two whole-stream orphan/unknown cases. Both
REMOVE matrices inherit the sixteen applicable ordinary/remote cases and retain
their existing exact error mappings. No unrelated failure can count as a rejection;
physical files and directories remain unchanged in each disposable mutation.

The [receipt](phase3-evidence/selection-journal.json) records the frozen reader,
untouched full replay, current negative matrices, original input hashes, Python
tests and extracted-archive replay. Four retained primary histories contain:

| Original history | Complete SELECTED appends | Journal callbacks |
| --- | ---: | ---: |
| 3-REPLACE including final same-view recovery | 14 | 56 |
| 4-REMOVE | 8 | 32 |
| 5-REMOVE | 9 | 36 |
| 4-REMOVE retirement SIGKILL/reopen | 11 | 44 |

The historical ADD reader is also replayed for compatibility. These are historical
native originals checked by the corrected reader, not fresh current-source
profile/process executions. The archive retains original producer metadata and
the final reader; optimized Python replay after relocation must reproduce the
same results and preserve every input member.

The final frozen reader passes all 1,767 Python tests, the complete REPLACE and
historical ADD replays, 159 REPLACE network negatives, 123 negatives for each
REMOVE profile, and the complete retained SIGKILL/reopen ballot composition.
The 405 exact negatives preserve all existing rejection cases. The first negative
driver missed the raw joining transport event form; its failed attempt remains
retained. A focused regression covers both raw and normalized forms before the
final-source matrices run again. No native experiment was retried.

The 43,336,362-byte archive retains 27,716 files and
4,599 directories. All four extracted originals replay
identically with optimized Python; every source/input inventory is unchanged.

## Remaining Phase 3 scope

This closes the reproduced SELECTED write omission, its authority timing variants
and ownership of the complete ordinary append family. It does not infer complete
whole-history coverage for other callback families or qualify a crash inside an
unfinished SELECTED append using the complete-transaction rule. Those prefixes
and their resumption require their own original process derivation.

A separate disposable-copy follow-up audit removes the first node 1
`CURRENT_FILES_FORCED` from initial current-generation open. The corrected
complete reader still accepts that copy. Its original, changed observation and
diagnostic result are retained for the next task. This is a concrete remaining
CURRENT-open coverage gap, not a claim that the native runtime omitted its force.

Full profile/fault/process cohorts, combined resource qualification and the frozen
S/N requirement mapping remain required. Phase 3 and complete physical/network/
process flags remain open. No Java, POM, workflow, timing/resource limit or cloud
behavior changed. Rollback reverts this reader/tests increment while retaining
the original audit failure and its precise scope.

The [initial CURRENT follow-up](PHASE_3_INITIAL_CURRENT.md) now closes that
startup omission for original voters; it keeps the remaining lifecycle scope open.
