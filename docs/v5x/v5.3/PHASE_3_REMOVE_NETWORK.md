# Phase 3 — REMOVE attempted transport and durable replies

This continues the two [continuous original REMOVE profiles](PHASE_3_REMOVE_PROFILES.md).
Their earlier producer recorded responses and deliveries, but did not enable the
existing request/terminal hooks. Those histories retain physical/lifecycle scope;
missing observations cannot be reconstructed from successful responses.

The explicit REMOVE test now enables `observeRequests` before `round.start()`.
It uses the existing transport observer to retain every send, server read,
response, client delivery and paired failure terminal in one ordered history.
Observation does not change runtime logic, deadlines, resource bounds or retries.
Each profile executes a new original bootstrap and uninterrupted native round;
old snapshots or substeps are not substituted into the new execution.

## Independent checks

`remove_network_evidence` first requires the complete original physical/lifecycle
reduction. It then composes the existing attempted-transport, byte-transfer and
full slot-storage readers with REMOVE-specific activation bindings:

- Every successful or failed attempted request has its original send/read/terminal
  chain. Receiver diagnostics match the observed failures; failures do not count
  as ACKs. The three-attempt bound counts both failed and successful sends of a
  request. Failed controls share the successful quorum operation's trace and
  originate after application and before publication.
- Original PROMISE/BASIS capture and force ordering precede each delivered promise.
  Selection references exactly those derived original sources. Every selected
  peer forces installation before replying; the proposer installs only after
  all peer ACKs have actually arrived. Activation sequences follow the native
  peer dispatch order; future-retention sequence 1 belongs to the local vote,
  with distinct remote sequences allocated in sorted governing-voter order.
- INTENT, FINAL and BARRIER bind ACCEPT/PROOF/APPLY/PUBLISH replies to their
  independently reduced records and complete successful storage transactions.
  Future-retention proofs precede publication and their exact revision/hash chains
  are reconstructed. REMOVE's retained lower endpoint comes from the original
  applied ledger, including deferred renewal debt, not the incoming intent.
- STATUS must echo its request nonce and describe a physically derived cut
  available during the observed request/response interval. It creates no voting
  or floor authority. Failed future-retention controls must also name the exact
  original operation, recipient, target and retained endpoints.
- Negative replay may change only observations. Reuse of a passing physical
  derivation requires every other file and directory to remain identical.

The reader preserves the legacy ADD/REPLACE paths and explicitly represents
REMOVE as having no joining identity. These three original one-slot control/edge
publications have no supplementary parent/ancestor application writes; the exact
applied member inventory still enforces their absence.

```bash
python3 -B -m scripts.v53.remove_profile_run target/v53-remove-network-5 --profile 5-REMOVE
python3 -B -m scripts.v53.remove_network_evidence RAW_DIRECTORY --profile 5-REMOVE --qualify
```

## Scope and evidence

The [batch receipt](phase3-evidence/remove-network.json) binds both new original
executions to the same producer source, compiled build and toolchain. Each test
completed once without retry; the retained source/build hashes are separate
from the final Python reader's source manifest.

| Original profile | Sent / delivered / failed attempts | Committed transfers | Original grants | Complete slot callbacks |
| --- | --- | --- | --- | --- |
| `4-REMOVE` | 883 / 868 / 15 | 269 | 8 | 1120 |
| `5-REMOVE` | 1180 / 1152 / 28 | 358 | 9 | 1260 |

Both profiles independently pass original physical/lifecycle replay with 16
physical negatives and network replay with 60 observation negatives. The latter
include correlated wrong sequence/trace, excessive attempts, missing terminal
diagnostics, premature replies and omitted/duplicated storage callbacks. All 120
network mutations reject for their declared reasons. The sealed archive checks
the exact file/directory set and every file hash; relocated replay with Python
assertions disabled produces exactly the same results on the same originals.
The 669-test relevant Python suite and the historical 11-slot ADD phase replay
also pass. That historical replay is compatibility evidence, not a new-source
ADD execution.

Initial reader failures are retained alongside the corrected source: the first
reader incorrectly assumed every activation/future request used sequence 1;
an intermediate result-assembly error was also corrected. Neither was a native
runtime failure, and no native workload was repeated to repair these readers.
The observer, validators and their tests are the only executable changes in this
batch; production Java, limits, retries and workflow configuration are unchanged.

The result stays **PARTIAL**. Complete export capability lifetimes and all maintenance/retention
callback composition, fresh-process cuts, other current-source profiles,
autonomous election scheduling and the frozen acceptance matrix remain required.
No public membership API, hosted dispatch or paid cloud execution is introduced.
Phase 3 remains open.
