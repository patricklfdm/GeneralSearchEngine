# Native count-refusal histories in carried-transition admission

Phase 3 remains **OPEN**. The v5 carried-transition catalogue adds two whole
SOURCE-count refusal/recovery histories to the existing fourteen histories.
It uses the [native refusal producer](PHASE_3_NATIVE_COUNT_REFUSAL.md) and the
existing optional hosted workflow; no new subset, Required gate or cloud entry
is introduced.

| Case | Exact JUnit method | Independent checks |
| --- | --- | ---: |
| `intent-application-halt-source-refusal` | `V53NativeApplicationRefusalTest#haltIntentWithSourceCountRefusal` | 280 |
| `final-application-kill-source-refusal` | `V53NativeApplicationRefusalTest#killFinalWithSourceCountRefusal` | 280 |

Each original contains the complete nine-family application-ACK crash/recovery
history and both refusal sidecar lifetimes. Original INTENT/FINAL, process death,
reopening the same disks, real receiver refusal, preserved admitted work and
fresh stable BARRIER remain indivisible. A node's original pool and physical
callback fix the nonempty GENERATION/SOURCE/APPLICATION counts 2/6/7. Temporary
CONTROL is returned and existing charges preserved before recovery continues.
This does not prove wire admission, full byte saturation or actual learner
pressure.

## Collection and replay contract

`scripts.v53.native_application_refusal_capture_history` implements the same
collection, replay and result-validation interface as the other native adapters.
Collection inventories the entire wrapper, checks all nine capture directories,
the two original process identities and the exact refusal sidecar file set. It
returns `PARTIAL`; collection alone provides no physical acceptance.

Independent replay first validates the complete original and every refusal
sidecar. Only then can any negative receive credit. The twelve probe-record
mutations keep their explicit `in-memory-probe-record` scope. The existing 268
captured-file and owner checks run in full against the same original; their
positive result must equal the first replay. The final result checks the exact
280-row vector, original inventory digest, complete distinct refusal lifetimes,
callback intervals, nonempty counts, cleanup, ownership preservation and scope.
The wrapper inventory is checked again after all replay. Both original owner
projections retain their bounded digests; original bytes stay in the archive.

The producer still requires one exact unretried JUnit method, successful native
and collection commands, immutable source, actual classes, portable tools and
reader binding. Execution/cohort/hosted receipt schemas advance to v5. A v4
receipt or the previous fourteen-history set cannot fill the new set. Source,
run, attempt, seed and archive checks apply unchanged to downloaded verification.
No previous development run is relabelled as a final-source member.

## Current scheduling and limits

The carried-transition subset now contains sixteen histories and **3,914 exact
negative checks**. Across twelve subsets, source inspection derives **566 whole
histories, 260 execution groups, 500 raw archives and 544 selected workflow jobs**.
These are scheduling counts, not results or frozen-scenario coverage. The
workflow's dynamic matrix supplies all sixteen original jobs and sixteen
verifiers, with its existing concurrency and failure-retention policy.

The machine qualification plan and source-catalogue digest include the new
entries. All five closure gaps remain OPEN. The frozen acceptance plan and
historical evidence indexes remain unchanged. Full feasible byte pressure,
remaining resource categories, admitted learner lifetime, operation-231
continuation and the complete final-source set still require execution/evidence.

## Development validation

Full replay of the retained FINAL/SIGKILL development original passed all 280
checks in 620.856 seconds: 3,301 original callbacks and six actual refusal probes
across both process lifetimes. All 10,613 original files (80,637,985 bytes) remained
unchanged. The bounded qualification is 105,270 bytes; collection is 1,928,076
bytes. No Java scenario was rerun.

All 174 focused Python tests passed (89 reader/cohort/hosted tests and 85 planning,
coverage and admission tests). Another 28 overlapping tests passed with assertions
disabled. All 529 preceding evidence indexes and the frozen acceptance plan remain
unchanged. An initial synthetic fixture failed because its test directories were
missing; that log is retained, and the corrected fixture suite passed. Documentation
links and source-derived scheduling counts also passed.

Results, current reader hashes, original source/build/toolchain references,
inventory and validation logs are indexed in
`phase3-evidence/native-refusal-cohort-development.json`; local detail is at
`target/v53-native-refusal-cohort/validation-summary.json`.

This is reader validation over the earlier development original, not a new
source-bound member: its earlier multi-method command cannot satisfy the v5
exact single-method producer contract. Synthetic orchestration tests also do not
count as native execution. The INTENT/halt original and complete final-source
hosted set remain pending.

## Rollback

Restore the v4 carried-transition methods, schemas, tests, qualification counts
and coverage-catalogue digest together. Keep the original fourteen histories,
standalone refusal producer/reader, runtime changes and all retained evidence.
