# Phase 3 — application recovery maintenance projections

Phase 3 remains **OPEN**. This batch derives campaign, FLOOR and ordinary
generation/source-retirement file states across an application-ACK crash and
recovery. It complements the separately qualified
[old application retirement captures](PHASE_3_CARRIED_APPLICATION_RETIREMENT_PREFIXES.md).
These projections are not observed file copies and do not qualify transient
bytes. No runtime Java, producer, resource limit, deadline or workflow changes.

## Keep the original deferred owner

Campaign file projection uses the same application-specific maintenance policy
as the existing original snapshot reducer. An owner with `applied-end` retains
its old ACK, certificate, generation and source references until the validated
old-end retirement finishes. The ordinary campaign projector keeps its existing
default policy. Projection is not invoked when the caller requests no campaign
file states.

The interrupted first lifetime derives accepted votes from the original carried
entry and payload before projecting maintenance. It binds every generation/source
retirement and FLOOR callback to its owner and original event index. The existing
local-generation pin rule is preserved when three original sources plus complete
FLOOR copies would exceed the seven-image ceiling. A nonvoter cannot acquire
projected maintenance callbacks.

Recovery validates the complete old application retirement prefix before deriving
the fresh slot. Only that validated storage prefix is removed from fresh-slot
projection; interleaved network observations retain object identity and original
global indices. Both the full old-end byte reader and the independent storage/
protocol/export/FLOOR/ledger/resource prerequisites remain available and strict.

The plan entry invokes the complete resource/history prerequisite first, then
requires all three families in both original process lifetimes. It refuses a
different kind/cut or duplicate callback ownership across families. Expected
states come from original admitted snapshots and transactions. They are never
read from captured sidecars. Ordinary vote, completion and replay collectors
remain unsupported by this adapter and explicitly reject instead of gaining
apparent coverage.

```bash
python3 -B -m unittest scripts.v53.test_native_carried_application_maintenance_plans scripts.v53.test_native_carried_application_protocol scripts.v53.test_native_carried_transition_forces
python3 -B -m scripts.v53.native_carried_application_maintenance_plans ORIGINAL_OBSERVED_RESOURCE_WRAPPER
```

The receipt is `PARTIAL`, with `capturedBytesQualified`,
`fullTransientBytesQualified`, `wholeRuntimeResourcesQualified`, `cohortAdmitted`
and `phase3Complete` all false. Callback coverage proves only the completeness of
the expected plan, not correspondence to native transient files.

## Observed development replay

The current reader snapshot is baseline `e3fd7d27` plus three modified and two
new Python files. It reuses the preceding batch's INTENT/halt original and the
earlier FINAL/SIGKILL resource original. Their recorded producer source/build
identities remain distinct; neither is relabeled as a new native execution.

| Original history | Campaign plans | FLOOR plans | Generation/source retirement plans | Replay and plan retention |
| --- | ---: | ---: | ---: | ---: |
| INTENT/halt | 623 | 1,343 | 977 | 54.330 s |
| FINAL/SIGKILL | 457 | 1,077 | 597 | 43.829 s |

All 5,074 projected callback states bind original indices across both process
lifetimes. Each original first passes storage/protocol/export/FLOOR/ledger and
resource replay. All original files remain unchanged: 5,023 files / 46,004,583
bytes for INTENT and 5,696 files / 43,735,810 bytes for FINAL. The result counts
expected states, not physical file observations or independent experiments.

Four of the initial six focused regressions fail on the preceding adapter's
unsupported behavior. The completed nine-test plan suite and adjacent suites pass
40 tests, also under disabled Python assertions; all 270 related carried-history
tests pass. These suites overlap. The documentation/planning checks pass, and all
394 preceding evidence indexes remain unchanged.

The [development index](phase3-evidence/carried-application-maintenance-development.json)
retains reader hashes, both original inventories, complete projected states,
compact results, prior producer records and test logs. No native producer,
Maven build, hosted workflow or paid-cloud run was started for this batch.

## Remaining obligations

Compose actual same-history campaign/FLOOR/ordinary-retirement captures with the
interrupted application and old-end retirement sidecars. Add original interrupted
votes, later application/publication, ledger and replay file families, then bind
physical charges and admit the complete application-ACK cohort. The twelve hosted
catalogues and their counts are unchanged. A final-source complete execution and
downloaded independent replay remain required.

Rollback removes the plan entry and its explicit maintenance collectors, restores
the adapter's unsupported-collector guard and removes the optional campaign
projection policy. No persisted runtime format or data migration is involved.
