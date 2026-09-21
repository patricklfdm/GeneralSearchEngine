# V5.1 Phase 4E: public recovery and lifecycle qualification

**Status:** implemented and locally qualified on `test/v5.1-phase4-recovery-lifecycle`,
based on accepted Batch D master `da9f3e9fe957e61c0fe45cf041431a5c4c74cd79`
(PR #195, exact-master CI `35570118695`). Complete Phase 4 acceptance remains open.

## Execution boundaries

`scripts/verify-v51-phase4-public-recovery.sh --skip-build` compiles external
consumers against packaged JARs and runs ten cases. Bootstrap, import, start,
mutations, queries, cancellation and close use public APIs. The observer can pause
an actual runtime boundary or interrupt a JVM; it cannot create authority or elect
a leader. Cloud, API, version and authority-format changes are outside this batch.

| Case | Execution and required observation |
| --- | --- |
| Imported genesis, halt | Published V4.4 exports ordered documents at sequence 41. Three public JVMs import it, acknowledge writes, halt the leader before publication of another proven write, elect a survivor and restart the retained voter. |
| Imported genesis, SIGKILL | The same import/failover schedule with controller SIGKILL at the observed boundary. |
| Missing promise | Move the required promise journal out of a freshly bootstrapped, stopped test voter; two independent public startup processes reject it without recreating authority. |
| Missing acceptance | The same rejection check for the acceptance journal. |
| Copied voter | Preserve the original stopped voter and copy another voter's exact directory into its path. Public startup must reject the identity mismatch. |
| Copied path | Copy a sealed voter to a new path and use that path in the public configuration. The bootstrap-bound admission must reject it. |
| Cancel queued mutation | Pause a captured read, enqueue a tagged bulk, cancel its original future, release the read and prove that no matching acceptance was forced. |
| Cancel admitted mutation | Pause after actual local ACCEPT force, cancel the original future, release the runtime and verify the chosen value survives subsequent reads/restart. |
| Close with pinned view | Pause a captured read. Close times out, a duplicate public handle cannot acquire the directory, and new mutations are rejected. Release the view; repeated close and a new owner then succeed. |
| Cursor after reads/mutation/rebuild | Three public TCP voters in one JVM run the same cursor program as a separate published V4.4 process. NO_OP reads preserve continuation; mutation and retained-handle reconstruction reject the old cursor, and a fresh page works. |

The five mutation/read/close cases use three simultaneous worker JVMs and a fourth
retained-restart process. Authority rejection cases use two separate public startup
processes each. The cursor comparison is explicitly a semantic lane with three
public voters in one JVM, not a multi-process crash claim.

## Independent checks and retained evidence

The client-only bounded history checker starts with the published import projection
when applicable. Cancelled mutation futures are uncertain operations: the model may
include each once or omit it, but cannot infer rollback from cancellation. The
existing operation/state bounds and real-time constraints remain in force.
`CANCELLED` is a harness observation of `CancellationException`, not a new public
mutation outcome or an assurance that admitted work was undone.

A separate physical checker decodes force records, receipts, selected quorum
transfers and published application bytes. It binds every successful read to its
own fresh NO_OP/captured view and attributes each tagged mutation at most once.
The lifecycle checker additionally requires the actual pause/cancel/release order,
absence of queued-cancellation acceptance, pre-cancellation force for admitted work,
and ownership rejection before a pinned close can finish. Missing cut/cancel/release
evidence must fail the negative checks.

Imported genesis sequence, document bytes/order and equality-index definition are
checked independently for all three voters. The source backup inventory must stay
unchanged. Failed-admission probes retain before/after inventories, rejected bytes,
separate PIDs and structured outcomes. Cursor results and original exception types
must agree with the separately compiled, hash-pinned published V4.4 control.

Every run retains source inventory, candidate/control hashes, client histories,
wire/force traces, exact pre-reopen archives, failures and per-case receipts. CI
uploads these artifacts with `always()`.

## Coverage and remaining work

This batch extends E01/E05/E07/E08/E09/E10 with imported failover, rejection,
cancellation, ownership and cursor evidence. It does not close all E01–E12 rows:
the remaining public mapping includes asymmetric/competing campaigns, ambiguous
selection and minority tails, recovery transfer/floor/deletion interruptions,
capacity/promise exhaustion and mixed-mode rejection. Internal Phase 2/3 evidence
continues to apply within its recorded scope. Full Phase 4 and protected Batch E
acceptance remain separate gates.

## Local validation

Base `da9f3e9fe957e61c0fe45cf041431a5c4c74cd79` plus this batch, 2026-09-21:

- Targeted reactor package passed 18 tests: public runtime, internal runtime and
  checkpoint regressions. This batch changes evidence/consumers, not production
  Java; it does not claim a new full-reactor run.
- Final recovery/lifecycle receipt:
  `target/v51-public-recovery/run.37ZU7C/evidence/receipt.json` — all ten cases
  passed. The five process cases each retained four voter JVM instances, with 40
  application calls total checked by both history and physical oracles and 41
  rejected negative variants. The four admission cases each used two independent
  startup processes and unchanged authority inventories. Cursor continuation and
  both stale-cursor exception types matched published V4.4 after retained rebuild.
- Existing public qualification:
  `target/v51-public-qualification/run.15HtPT/evidence/receipt.json` — all six
  halt/SIGKILL cases and the published V4.4 rich-query/backup comparison passed
  with the updated shared history/observer helpers.
- All 78 V5.1 Python tests passed, including imported initial state, uncertain
  cancellation, precise lifecycle cut binding and rejection-checker negatives.
- CI execution/always-retained artifacts, shell/Python syntax, the 27-document
  contract, changed Markdown links and whitespace checks passed.

Candidate core JAR SHA-256:
`f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
Candidate replication JAR SHA-256:
`2300c45c8f2bb5596d96ffe6479254b50a7fd2f87df81a3ba592c67898c2db4f`.
Published V4.4 control SHA-256:
`0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`.

Exploratory compiler/fixture failures remain retained and are not qualification
results. Each receipt binds the source inventory at execution; this summary is
written afterward. Protected Batch E and full Phase 4 acceptance remain open.
