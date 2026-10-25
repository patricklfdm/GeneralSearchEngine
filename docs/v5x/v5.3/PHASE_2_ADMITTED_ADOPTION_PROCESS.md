# Admitted removed-voter adoption process recovery

Status: locally qualified for the four fixed profiles. This batch extends the [admitted cross-view
storage profiles](PHASE_2_ADMITTED_CROSS_VIEW.md) with actual fresh-process
termination and recovery of the removed voter. It does not enable a public
membership runtime or learner transport.

Each original group is publicly bootstrapped with five or four voters, from
EMPTY or a verified typed backup. Real admitted owners produce RESERVE through
INTENT, a joint selection and the surviving majority's certified FINAL. The
removed owner remains at its original INTENT generation. Its exact admission,
root, history, identity, parent directories and received FINAL bytes stay fixed.
The failure matrix restores only that node's original files between cases.

Nineteen adoption boundaries are terminated both by `Runtime.halt(73)` and by an
external SIGKILL after the worker's explicit handshake. Recovery is interrupted
again before selector force, or during reopen once the original selector was
already renamed. A third fresh worker completes recovery, repeats adoption
without changing the manifest, and verifies that the removed identity cannot
obtain a new voting grant. The SIGKILL cases also verify the original exclusive
lock while the worker is alive. Every completed worker closes all reservations.
The four profiles comprise 152 cases, 456 fault/recovery/resume workers and 76
separate lock probes. These are process-death tests, not power-loss tests.

The independent Python reader first replays the complete original cross-view
reference, including its final typed DATA and BARRIER. It then derives the
received packet, original observations, exact adoption generation and promise,
all three physical snapshots per case, force/death ordering, exit codes and lock
path. It requires original admission records to remain unchanged. Twelve targeted
evidence mutations must fail for their expected reason after the complete
original matrix passes. Normal and optimized Python and an archive relocated
outside the original producer workspace must return the same result.

The first diagnostic replay exposed an offset error in this new reader: a backup
plan includes a source path after its operation path. The corrected reader binds
paths by the original target identity and excludes that source path. The failed
reader/log remain retained; the unchanged Java evidence is replayed rather than
rerun. Six focused Python tests cover original-first validation, target binding,
foreign journal replacement, lost original authority and absent fault cuts.

Retained work: `target/v53-admitted-adoption-process/`. The [source/build/evidence index](phase2-evidence/admitted-adoption-process.json)
binds source inputs, compiled producer classes, raw inventories, normal and
optimized replay, archive replay and diagnostic failure. The runtime still has
the same production classes as the corrected mixed-context storage batch.
Maximum application bytes, metadata completion headroom and the Phase 2 closure
audit remain separate outstanding qualifications.
