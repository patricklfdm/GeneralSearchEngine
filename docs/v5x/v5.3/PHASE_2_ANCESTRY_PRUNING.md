# Six-to-one ancestry pruning process qualification

This is a private Phase 2 storage qualification. Phase 2 remains **OPEN**.
The production behavior was introduced by [original selected-source retention](PHASE_2_SELECTED_SOURCES.md).
This batch adds retained crash evidence and independent replay without changing
runtime logic, frozen bytes, resource limits, public APIs or workflows.

## Exact scenario

Three separate local owners retain original selected BASIS frames at cut 8. Their
initial generation has six historical RANGE bridge groups, with lower endpoints
1 through 6 and upper endpoint 8. That earlier history is an explicit conditional
fixture. The new grant/selection, ACCEPT/PROOF/certificate and forced application
ends are obtained from actual local owners. The certified operation is a BARRIER
at index 9, so the application image and sequence must remain unchanged.

The next generation needs only the 8→9 bridge. It preserves every original
selected frame and omits the six obsolete groups only in the new materialization.
The complete old generation, source packets, original selection and grant journal
must remain byte-for-byte intact. No old source or generation retirement is
authorized merely by this pruning operation.

## Process boundaries and replay

The declared matrix uses halt and external SIGKILL at five boundaries:

- Exact `selected-sources.gsr` write, before its force.
- Force of that exact member, before later generation members.
- Published selector force.
- First covered applied-end file deletion.
- Empty covered-vote candidate prefix write.

Every case interrupts recovery once more, then reopens in a third fresh JVM.
Before selection, the second cut is candidate-image write. After selection, it
is covered-vote candidate force. The worker labels the exact member by its
manifest-sorted position; it cannot confuse the first generic metadata write
with the selected-source write. These labels are test observations only.

The Python oracle derives the complete expected generation from original sources,
real original votes and the two peers' forced ends. It checks all six old groups,
all three original selected frames, original source images and manifest inventories.
It independently projects the BARRIER catalog, new RANGE, sole parent bridge and
coverage. Exact write/force/deletion order and entire surviving inventories are
compared at both crashes and completion. The seven-image and metadata bounds
remain checked. The original must validate before negative mutations; relocated
replay must return the same result.

## Local commands

All **10 cases / 30 fresh JVMs**, **14 original-first negatives** and portable
replay passed, both normally and with Python assertions disabled. Earlier parent
and distinct-source ancestor evidence still replays through the shared physical
model (24 cases, 22 negatives). These are historical raw observations replayed
with the current Python model, not new JVM executions. The
[source/build/evidence index](phase2-evidence/ancestry-pruning.json) retains both
the successful matrix and the two corrected test-setup failures.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53AncestryPruningTest -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.ancestry_pruning_evidence <printed-v53AncestryPruningEvidence>
```

Use the exact directory printed by that execution, not an older successful run.
Retain unsuccessful development runs as well as the qualified source/build inputs.

## Limits

The six historical groups and bootstrap are conditional fixture authority. Current
force observations are real local process observations; this does not establish
power-loss durability, network authentication, a public runtime, same-round
continuation, or coordinated long-lived source/floor retirement. Those obligations
remain in the [Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md).
