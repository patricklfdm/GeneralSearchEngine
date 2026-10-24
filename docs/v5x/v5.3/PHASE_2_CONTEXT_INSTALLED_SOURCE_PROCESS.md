# Process recovery of an obsolete installed source

Phase 2 remains **OPEN**. This qualification extends the
[repeated context installation lifetime](PHASE_2_CONTEXT_INSTALLATION_LIFETIME.md)
with real process death while reclaiming an intermediate original source.

The producer first executes the actual three-owner six-round lifetime. It takes
node 1's state immediately after generation 23 replaced and retired generation 22:
the exact original ballot-20 vote remains backed by source 23, the governing floor
is still 21, and source 22 is now obsolete. The context, current generation and
complete floor remain protected throughout source reclamation.

Fifteen cut positions cover creation and forcing of the retirement decision,
journal compaction, listed source-member deletion, directory removal and final
cleanup. Each position runs both `Runtime.halt(73)` and externally delivered
SIGKILL. The SIGKILL producer waits for the exact cut marker and checks the live
replica lock before killing its owner. A second fresh owner halts during context
source resealing. A third opens, completes the exact retirement, and returns the
new ballot-23 ACCEPT only after its force, context withdrawal and floor cleanup.
The exact duplicate returns the same receipt; the ENTRY still has origin 20.

There are 30 cases, 90 workload worker processes and 15 separate live-lock probes.
The producer checks bounded reservations at every storage callback, a peak of
seven application images, and zero leaked reservations after close. The independent
Python replay derives each physical prefix and complete event sequence from the
original three-owner lifetime. It checks the retained original before applying
eighteen evidence mutations, with normal, optimized and relocated replay.

The [source/build-bound index](phase2-evidence/context-installed-source-process.json)
retains the original logs, raw snapshots, worker classes and replay results. This
batch does not change production Java, resource limits, formats, POMs or workflows.
The qualification uses small images and a conditional historical bootstrap;
process death is not power loss. Selected-generation installation and intermediate
generation retirement need their own process qualification. Maximal capacity,
admitted bootstrap-to-lifetime and prescribed cross-view profiles remain pending.
Public online membership stays disabled.
