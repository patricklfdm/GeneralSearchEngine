# Phase 3 — original REMOVE retirement across process death

Status: complete observed generation/source retirement callbacks are qualified
for the retained v2 `4-REMOVE,RETIREMENT_BORROW_PREFIX_WRITTEN,kill` member.
This extends [continuous retention](PHASE_3_REMOVE_PROCESS_RETENTION.md).
The other process members, ballot-force composition, complete observation
coverage and the seven-profile/frozen acceptance mapping remain OPEN.

## Original transaction and recovery

Physical, attempted-network, temporal-export, maintenance-floor and continuous
retention replay run first. Each retirement starts from its original installed
or published generation, the actual acquired floor copies and the independently
evolving peer ledger. Possible and renewal endpoints require exact original
coverage. A repeated snapshot cannot silently become another transaction seed.

The reader derives generation reclamation, including the capacity-driven copy or
borrow decision, followed by superseded-source retirement and journal rotation.
Every intermediate derived state is checked against the unchanged physical
capacity. Every observed callback is consumed exactly once, with its original
owner, order and shape. Callback counts alone do not establish completion.

The killed process ends at the first occurrence of the requested cut. Recovery
finishes that original interrupted transaction only. Its resulting complete file
tree must equal the original reopened snapshot. The resumed retained-floor
maintenance consumes this derived recovered tree, dropping only the old floor
subtree; it cannot reload the pre-retirement snapshot. For a source/journal cut,
the generation transaction is already complete and must not run again.

| Observation | This original member |
| --- | ---: |
| Generation retirements | 16 |
| Source retirements | 11 |
| All retirement callbacks | 951 |
| Recovery callbacks (included above) | 55 |
| Generations borrowing original images | 9 |
| Generation members processed | 123 |
| Interrupted transactions | 1 |
| Maximum derived physical images | 7 |

These are observed results, not new workload parameters. This batch does not
claim that every transient derived byte was independently captured on disk.

## Qualification and scope

```bash
python3 -B -m scripts.v53.remove_process_retirement ORIGINAL_V2_PROCESS_ROOT \
  --qualify --workers 4
```

The [receipt](phase3-evidence/remove-process-retirement.json) binds the original
producer, frozen reader, raw inputs and portable archive. Thirty-six negatives
remove, reorder, duplicate or forge retirement callbacks. Each preserves physical
files, wire/failure bytes, directories, all other observations and successful
continuous-retention replay. It must then fail the retirement reader for the
exact declared reason. The full unmodified prerequisite runs first; the mutated
full prerequisite is not counted as the target rejection.

Original and extracted optimized-Python qualification must be identical, with all
input hashes unchanged. Twelve focused tests cover first-cut recovery, all six
source/journal cuts, retained-floor reuse, endpoint coverage, transient capacity,
exact callbacks and rejection isolation. All 1,684 V5.3 Python tests passed at
this reader snapshot. The initial test fixture's recursive mock failure remains
retained separately; it is not a native execution failure or acceptance result.

`retirementRetentionCompositionQualified=true` is limited to this layer and
member. `completeObservedCompositionQualified`,
`originalObservationCoverageComplete`, `transientRetirementBytesQualified` and
`phase3Complete` remain false. The allocator/promise force audit is the next
independent obligation. No production Java, workflow or cloud execution changed.
Rollback removes this reader, its tests and documentation only.
