# Required-four continuous retention and ballot ledgers

`scripts.v53.required_four_ledgers` composes peer, learner, future-retention and
allocator/promise readers behind the complete required-four maintenance entry.
All four use the same original topology, generation windows, captured sources,
control exchanges and publication transactions. Mutable chain and maintenance
state remains separate; no reader can seed another from a reported end snapshot.

The shared ledger derivations start from original bootstrap bytes, apply actual
force-bound transactions across JOINT, FINAL and the successor barrier, and
compare the continuously derived state with cold originals. All six owners must
appear in the final revisions/counters, including offline nodes 4/5 and departing
node 3. A future covering floor can protect old bytes without falsely becoming a
same-cut peer ACK. Required-four peer maintenance uses the original-pin force
plan from the preceding batch and records each floor input once.

The negative matrix retains all 86 existing component cases: 20 peer, 26 learner,
19 future and 21 ballot cases. Three existing applicability conditions are
explicit: a joining-owner write-scope mutation requires an original joining
write, and two adoption mutations require the original adoption fence/promise.
Absence is reported as `NOT_APPLICABLE`, never as an executed rejection. Every
other missing target fails the matrix.

Original physical/network/export/maintenance and all four chains must pass before
any mutation. Negative copies can change only designated ledger callbacks;
physical files, wire and all other observations remain unchanged. Historical
peer removal markers are converted to exact omissions, without discarding any
unrelated event. Mutated prerequisites are not requalified: the intended chain
reader must reject with the exact registered reason. Accepted mutations, unrelated
errors, protected-file changes, missing targets or failed worker tasks fail the
matrix. The default is one worker; explicitly requested parallel replay is bounded
to four isolated copies.

```bash
python3 -m scripts.v53.required_four_ledgers "$ORIGINAL" --qualify --workers 1
```

## Current evidence and remaining work

Twelve conditional tests cover common original context, independent mutable state,
pin and covering-floor dispatch, all six final owners, original-first admission,
negative applicability and mutation isolation. Real temporary files exercise
wire/authority protection, unrelated callbacks, exact omission and rejection
reasons. Initial test fixtures used noncanonical JSON; corrected fixtures and the
initial failure log are retained in the
[development index](phase3-evidence/required-four-ledgers.json).

These are reader-composition tests, not a native continuous-chain qualification
or 86 executed negatives. Corrected-source network/export/maintenance/ledger
replay still requires a fresh complete connection-bearing original; earlier raw
histories remain unchanged and are not upgraded. No long native run or hosted
workflow was launched for this batch.

Whole-runtime resource maxima, native process-fault schedules, frozen coverage
and final-source admission/execution remain open. The twelve hosted subsets /
544 planned histories are unchanged. Phase 3 is not closed. This batch changes
only Python validation and documentation; runtime, limits, record/wire formats,
workflows and V5.2 cloud execution are unchanged.

Rollback removes the optional reader/tests and its documentation/plan entries.
Existing component and required-four maintenance readers remain usable.
