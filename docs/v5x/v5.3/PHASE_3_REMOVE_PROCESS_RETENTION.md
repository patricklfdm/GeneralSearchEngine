# Phase 3 — continuous REMOVE retention across process death

Status: continuous peer and future revision chains are qualified for the retained
v2 `4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill` member. Complete retirement
callback composition, the remaining process/profile matrix and Phase 3 remain
OPEN. This extends [maintenance-floor recovery](PHASE_3_REMOVE_PROCESS_MAINTENANCE.md)
without changing production Java or rerunning the original native history.

## One continuous state

Physical, attempted-network, temporal-export and maintenance-floor replay must
pass first. The reader derives the bootstrap ledgers independently. These reach
the admitted network cut with revision zero; the network cut is not a new ledger
seed. All later installed, applied, published, interrupted, reopened and closed
snapshots are comparisons against the evolving state. None replaces that state.

Peer changes derive from the exact original acquired copies, view reconciliation,
frozen selected-source plans and original publication proof. An unchanged plan
consumes no write. A changed plan consumes exactly one complete original
write/force/rename sequence and advances the revision with the exact previous-byte
hash. Original grant sources must contain the derived ledger at capture time.

Future targets derive from original lower endpoints and application records.
Recording and clearing preserve the exact revision predecessor. Local recording
ACK precedes its send; remote ACK follows force and precedes the original offered
response. Promotion precedes clearing and publication completion.

All six opens bind active-file and directory resealing to their original owner
and ordered CURRENT/accept recovery boundaries. Installation also revalidates
CURRENT; that validation alone is not another open. The resumed proposer's peer
ledger remains at the independently derived revision three after the crash; its
next maintenance reuses the original floor without resetting that ledger.

| Ledger | Writes | Causes | Original comparisons | Opens |
| --- | ---: | --- | ---: | ---: |
| Peers | 43 | 27 maintenance, 8 selection, 8 publication | 104 | 6 |
| Future targets | 22 | 14 record, 8 clear | 86 | 6 |

Peer final revisions are 16/16/11/0 for nodes 1–4; future revisions are 8/8/6/0.
The inactive fourth voter remains included in initialization, open and final-byte
checks. Eleven new frozen-source peer ledgers are compared. Counts describe this
original member, not fixed acceptance thresholds or a new native experiment.

## Qualification and scope

```bash
python3 -B -m scripts.v53.remove_process_retention ORIGINAL_V2_PROCESS_ROOT \
  --qualify --workers 4
```

The [receipt](phase3-evidence/remove-process-retention.json) binds the original
producer, separately frozen reader and portable raw archive. Nineteen peer and
eighteen future negatives exercise missing/reordered/duplicate/unbound writes,
wrong owner or scope, maintenance/selection/publication ordering, ACK/completion
ordering and resumed reseal order. The complete unmodified prerequisite runs
first. Each copied negative preserves all physical files, wire and failure bytes,
directories and non-target normalized observations in order. It then must fail
the target retention reader for the declared exact reason. The mutated full
prerequisite is not rerun or counted as that rejection, because reseal callbacks
are also checked by the process-lifecycle layer.

The initial development negatives that broke child STORE schema or crossed the
original killed-process boundary are retained as failures. Corrected mutations
use original parent-owned callbacks so the unchanged parser/process guards pass
and rejection comes from the intended retention rule. Unrelated failures never
count as successful negatives. Original and extracted optimized-Python replay
must return identical results with every input hash unchanged.

Ten focused guard tests cover continuous-state comparisons, repeated open
boundaries, write reuse, mutation isolation and original-first checks. All 1,672
V5.3 Python tests pass. No workflow, cloud execution or runtime format changes.
The result stays `PARTIAL`: `retentionRevisionCompositionQualified=true` belongs
to this layer; nested earlier receipts retain their original narrower flags.
The full process matrix and seven-profile/frozen acceptance mapping are still
required. Rollback removes this reader and its documentation only.
