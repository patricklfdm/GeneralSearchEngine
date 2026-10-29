# Phase 3 — replace the learner head and reclaim B

The selected B and pending reused A now participate in an original head
replacement. Both actual typed owners must match the recorded source, generation,
receipt and physical inventories. The complete candidate is forced while B's
head remains active; its original inode replaces the active head atomically and
is re-forced before returning A as current. This revokes old B handles. A remains
nonvoting, and its current typed acquisition capability is unavailable until the
covered B retirement and new vacancy have completed.

The new selector records B's exact source/typed deletion inventory and retained
plan/installed metadata. Those metadata files stay in the slots root after B's
source and typed backup disappear: they are needed for conservative recovery
accounting and the next reuse. Unknown or replaced members and an unbound retired
plan candidate are refused. Deletion never includes A's selected files.

Cold recovery distinguishes an intact B plus a complete A candidate from an
already-selected A. The former still requires actual B/A typed owners to finish
selection; it is not silently promoted. The latter validates A independently and
can finish covered B deletion even when some old members are already absent.
A new original clear record replaces the old vacancy only after B removal and
parent forces. Old resources release after the new clear is forced. A complete
new clear permits cold recovery to skip absent B charges; missing paths alone do
not. The immutable seed metadata and lock remain owned throughout.

The [A27 contract](PHASE_3_CONTRACT_AMENDMENTS.md#a27--replace-the-selected-learner-head-and-retire-b)
adds a bounded replacement-head schema under the same two file names. It does not
add authority directories, append-only history, generation slots, image allowance
or a timing extension. The conservative metadata allowance stays 1852 KiB.

## Evidence and remaining work

[Component evidence](phase3-evidence/learner-rotation.json) records exact inputs,
compiled production identities, tests and preserved attempts. Conditional voter
histories use original files and actual core decode. They cover original-candidate
and renamed-head recovery, partial-candidate refusal, handle revocation, covered
B reclamation, copied selectors and recreated old roots. These are synchronous
exception cuts, not native consensus or halt/SIGKILL qualification.

This implements selection of sequence-2 A and B retirement. Subsequent B-plan
replacement/reuse, repeated alternating cycles, cancellation, matching local
INTENT and autonomous READY remain OPEN. The next installation is explicitly
refused until its original replacement plan is implemented. Long native and
process-death histories, including new-vacancy candidate cuts, remain in the
[deferred queue](PHASE_3_DEFERRED_ACCEPTANCE.md). Phase 3 is not closed.

The final frozen-source component execution passed all four requested test
methods with zero failures/errors/skips: the three replacement/retirement methods
and the existing TCP reuse/cold-reopen regression. The two selector cuts share
one method but each creates its own complete fixture history. The preliminary
execution was stopped after the final source added the uncovered-retired-candidate
refusal; its distinct source and partial logs are retained and do not qualify the
final build. No full reactor suite, native history replay or process-death matrix
was rerun for this component batch.
