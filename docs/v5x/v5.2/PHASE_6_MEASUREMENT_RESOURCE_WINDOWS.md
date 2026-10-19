# V5.2 Phase 6K asynchronous boundaries and resource windows

**Status:** local integration qualification passed. Formal M01–M04 execution
and the complete machine freeze remain pending. This stage retains the existing
short smoke's three-second window and ten calls; it is not a shortened M01 run.

## Keep the original offered clock

The offered-load driver can schedule named markers alongside business requests.
At the same due time, the marker is submitted first; neither marker nor business
submission waits for its response. Any control overhead therefore appears as
lateness against the original business due time. No schedule is reset, no call is
retried, and the driver waits through the original end boundary.

Each marker retains its original due time, actual offer/submission times and the
original futures for every target. A partial transport failure preserves already
submitted futures, marks the failing control task and retains the undispatched
suffix. Draining uses the same common observation bound as the business calls;
an incomplete marker prevents successful qualification.

Independent replay requires exactly the declared marker names, offsets and target
set, unique operation IDs, matching sample-mark commands/responses and complete
controller observation. The marked short fixture uses warmup-start at zero,
measured-start at 500 ms and measured-end at three seconds. The later M01 entry
must bind its own unchanged zero/60/180-second schedule in the execution plan.

## Resource counters at actual process boundaries

Every process retains its own sampler START, three MARKs, periodic observations
and STOP. The corresponding controller commands must surround the offered interval
and match the actual sample bytes. The three marks must be the operations submitted
by the driver at the declared boundaries; a nearby unrelated sample cannot replace
one. Worker and controller clocks are never treated as one clock.

The report keeps whole-session results and separate warmup/measured observations.
CPU and allocation deltas use the actual start/end marks of each window. Sampled
heap, non-heap, thread, retained-byte and queue high-water values use observations
between those same boundaries, including the endpoints. Unsupported counters stay
explicitly incomplete; they cannot become zero deltas.

Each window records nominal controller duration, observed process-local boundary
spacing, both sample collection intervals and controller marker dispatch lag.
These intervals can differ because of scheduling and control delivery. The report
does not synthesize exact simultaneity or turn sampled peaks into exact maxima.
All resource values remain process-wide and include observer overhead.

## Qualification

Deterministic tests cover all 1,980 offered calls with nine unresolved marker
futures, delayed markers without shifted due times, partial target failure, missing
targets, altered boundaries, separated window/session deltas and unsupported
allocation. The real five-mode short gate additionally checks original/relocated
physical authority, query truth, complete lifecycle, marker binding and window
resources. Large-package replay and all previous negatives remain required; a new
negative changes the measured-start marker into a duplicate warmup-start.

Complete `run.Q7JAh5` passes all five modes: 15 JVMs, 55 reads, 15 updates, 45
marker commands, 120 samples and 30 process/window summaries. All original and
relocated physical/query checks and 200 negative checks pass. The 4,383-file large
package passes baseline/raw/relocated replay with 24 negatives each.

All 138 V5.2 Python tests pass. CI inventory, documentation contract, changed local
links, shell syntax and whitespace checks pass. No new Maven reactor or protected
hosted result is claimed. The execution binds base
`65840511c568a53ee5192c9e7f1d758de2a4321b` and checkout
`c3fd51de3be1c3ca9b4bb5d2bdb9dd8a3dbc49efc83406ed43b8513931f8b37a`.

Local evidence and original failures are retained at
`target/v52-measurement-markers`. The full measured entry and M02–M04 schedules are
still required before the complete machine freeze and formal measurements under
the [local development sequence](LOCAL_DEVELOPMENT_SEQUENCE.md).
