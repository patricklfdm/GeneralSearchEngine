# V5.2 Phase 6AN complete histories over installed Python

The [installed Python backend](PHASE_6_REMOTE_PYTHON_RUNTIME.md) now selects the
existing whole controller for each exact frozen history: five untimed modes,
26 M01–M03 profiles and two M04 faults. Selection admits only the 33 declared
names; empty, duplicate, partial or invented profiles reject. This does not split
continuous histories or combine evidence from different source bindings.

The source descriptor pin propagates through delivery, bootstrap, every voter
owner, retained generation-2 restart and prepared partition channels. An endpoint
copies its validated pin so later caller mutation cannot change a launch. A
retained second generation requires the exact restart execution marker; an
arbitrary nonempty marker grants no additional scope.

## Execution and evidence

Formal histories use their existing nonretrying client and unchanged offered
clock. Their original export budgets apply. Restart keeps its original one-shot
crash owner and terminal-response query. Partition retains its preconnected
parallel cut/heal barrier, all six original receiver transitions, lost-response
queries and separately checked cleanup. No business operation or workload is
retried. Existing original/relocated physical, query, history and fault negatives
run alongside the installed-source negatives. Partition also keeps its lifecycle
and selected-basis negatives. PASS is written only after process and SSH daemon
cleanup succeeds.

```bash
scripts/verify-v52-phase6-installed-histories.sh --skip-build
```

The default local gate runs four complete histories in order: minimum-policy
untimed smoke, M03 P=4, retained leader restart and follower snapshot recovery.
Each has fresh owned paths; all four must retain the same controller source.
The receipt records each original count, archive hash and negative-check count.
Minute heartbeats continue through package delivery, preparation, workload and
physical replay. A failure preserves the partial receipts and stops the gate.

An explicit subset can be selected for diagnosis with
`python3 -m scripts.v52.remote_python_histories OUTPUT --history EXACT_NAME`.
Such a subset qualifies only the names it records, not the complete default set.
Full M01 qualification remains a separate long gate; accepting its profile does
not claim that all 26 formal histories have executed on this backend.

## Validation status

The complete four-history gate passes in 577.630 seconds: 24 original reads,
15 updates, 338 negative rejections and 13 stopped services/JVMs. Original and
relocated physical/query validation passes for every history. All 508 V5.2 Python
tests pass on the final development worktree. Eight aggregate tests include
failed-history retention without retry or advancement, source substitution,
source drift and explicit subset scope. The source-drift regression first fails
on a history incorrectly left as PASS, then passes after its terminal status is
corrected; the aggregate already failed in both versions.

| Complete history | Seconds | Reads / updates | Negative rejections |
| --- | ---: | ---: | ---: |
| Minimum-policy smoke | 148.936 | 11 / 3 | 94 |
| M03 P=4 | 114.079 | 5 / 4 | 64 |
| Retained leader restart | 151.880 | 4 / 4 | 86 |
| Follower snapshot recovery | 161.978 | 4 / 4 | 94 |

The immutable real-run snapshot is
`366990a004d6ca2d1989f539f59568d7ebd5974e`, checkout
`757542013de76a8a846f044f8267c6b1d7c5e134071135122ce6060632edc55f`.
It is a local qualification fixture, not an upstream or protected CI commit.
The receipt remains under
`target/v52-remote-python/qualification-checkout/target/v52-installed-histories/run.IrA6Qf/evidence/receipt.json`.
`target/v52-remote-python/installed-histories-validation-summary.json` retains
its source, receipt hash and totals; `installed-histories-executed-files.json`
retains the executed code hashes. The final development code differs only in the
aggregate's failed source-drift status and its four additional regression tests;
all runtime, transport, workload and replay implementations match. The receipt is
not rebound to the development commit. No production Java or frozen parameters
change in this stage.

This is single-host loopback SSH qualification: `sharedPythonCheckout=false`,
`independentHosts=false`, `qualifiedMeasurement=false`,
`fullRemoteQualification=false`, `paidCloud=false`. Independent-host identity and
clock routing, complete owned members, protected exact-source CI and fresh cloud
admission remain open.
