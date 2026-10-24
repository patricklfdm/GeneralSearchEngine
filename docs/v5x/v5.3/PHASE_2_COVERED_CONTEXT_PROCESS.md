# Covered protected-context process recovery

Status: local fresh-process qualification **PASS**. Phase 2 remains **OPEN**.

This follows the [covered-context owner correction](PHASE_2_COVERED_CONTEXT.md)
without changing production Java. An actual public EMPTY bootstrap supplies three
voters. Each certifies the first entry, captures a later selection and retires its
original generation/source under a retained context and floor. A majority then
publishes that entry. The lagging voter selects the exact advanced prefix while
its original certified vote remains protected by the context.

The new driver terminates that voter at eleven installation/cleanup boundaries,
once with `Runtime.halt` and once with an external SIGKILL. Each of the 22 cases
then interrupts recovery in a second fresh JVM before a third process completes.
The gate therefore records 66 workers and eleven independent lock probes while
the kill target is alive. Snapshots are copied only after the target exits;
the live worker never opens and closes another descriptor for `replica.lock`.

The independent reader reconstructs admitted originals, actual phased ownership,
the retained context and floor, majority publication and selected installation.
It derives all three crash states from these bytes before comparing the saved
inventories. The complete force/death traces, exact exit codes and cut names,
kill handshake, original admitted lock path and final result scope must match.
Cleanup cannot emit an old ACK. Completion clears only the exact protected vote
and context; it preserves the source, governing floor and installation authority.

One Java test drives the full process matrix. Twenty-five Python tests cover this
reader and its context/staging dependencies. Twenty prescribed corruptions are
rejected for their exact reasons after validating the unmodified evidence.
Normal, optimized and relocated replay agree. The source/build-bound
[evidence index](phase2-evidence/covered-context-process.json) retains the logs,
original bytes and production class comparison with the preceding owner gate.

This is process-crash qualification on the local filesystem. It does not emulate
power loss or claim maximal bytes, complete cross-view lifetime, mixed-original
covered completion, or an enabled public runtime. Typed DATA semantics are checked
by the Java producer; Python validates their retained bytes and scope. The
[closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) still governs Phase 2 completion.

## Reproduction

```bash
/opt/maven/bin/mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53CoveredContextProcessTest -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m unittest scripts.v53.test_covered_context_process
python3 -m scripts.v53.covered_context_process_evidence "$EVIDENCE" --portable
python3 -O -m scripts.v53.covered_context_process_evidence "$EVIDENCE" --portable
```

Use the `v53CoveredContextProcessEvidence` path from this build. Do not substitute
older raw states or receipts for a different source or compiled runtime.
