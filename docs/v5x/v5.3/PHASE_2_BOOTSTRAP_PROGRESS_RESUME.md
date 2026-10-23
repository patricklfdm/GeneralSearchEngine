# Phase 2: finish bootstrap around progressed completed nodes

Status: private coordinator recovery locally qualified; Phase 2 remains **OPEN**.

After a crash following the first local seal, that sealed voter can legitimately
open and progress before the other seals are completed. The previous strict
initial-layout transaction could not recover that group without rejecting the
runtime's changed counter/log. The coordinator now selects an explicit recovery
mode that leaves completed targets with their live owners.

Only an **exact complete original COMMITTED journal** permits this mode. At open,
the transaction fixes the set of targets already bearing an exact active seal.
It snapshots and guards their original ROOT/GENESIS/NODE, preparation, admission,
seal, directory and lock identity. It does not walk their mutable descendants,
open their lock descriptors, reseal payloads, force admission files, or create or
rewrite their directories. Existing core directories are allowed. Pending seals
on an already completed target remain a refusal.

Every unsealed target still requires the exact original prepared payload, absent
core, exclusive owner and original prefix/force/rename sequence. All target
admissions must already be complete once any seal exists. A missing seal with
mutable progress is refused by the strict prepared checks; no counter/log is
restored to genesis. Missing or altered admission on either side is refused before
completion writes. Exact request/configuration checks still precede resume work.

The operation's own original journal may be re-forced during recovery. Its initial
completion budget includes all original payloads and admissions. Concurrent runtime
files of completed targets belong to their separately bounded store owners; they
are neither charged as new bootstrap files nor treated as initial payloads.

The original component `applyAdmitted` and `readAdmitted` retain their strict
inventory/trace profile. Only the private coordinator's explicit resume selects
completed-target handling. No public API, learner admission or runtime is enabled.

## Validation

Five Java methods cover all six size/source profiles, real grant/counter/core
progress on the first sealed voter, a second interruption during the next seal,
complete recovery while the first owner stays live, and idempotent completed-group
resume. The original running counter/log/source/core remain unchanged; the owner
can reserve another counter afterwards. External JVM probes confirm its lock
survives recovery. Evidence copies stat empty lock files instead of opening them.

Lost seal after progress, changed unsealed counters, torn admission/preparation/root
on completed or pending nodes, another owner on an unsealed target and immutable
inode replacement during recovery are refused. The latter also invalidates the
live store's next write rather than silently accepting a replacement record.

The independent original-first replay derives all initial bytes and all three
force traces, models actual grant/source/counter progress, and checks exact
initial/before/second-crash/final inventories and original result. Sixteen negatives
include rollback of the progressed counter, omitted admission and altered force
order. Existing component/coordinator profiles remain independently replayed.
Actual counts, artifacts and source provenance are recorded in the
[evidence index](phase2-evidence/bootstrap-progress-resume.json).

## Remaining boundary

These are repeated exception interruptions and actual external lock probes, not
halt/SIGKILL of the typed coordinator. The all-size typed fresh-process matrix is
next, including this partial-group progression. Public offline entry, transferred
pending-context lifetime, maximal/cross-view resource qualification and the complete
Phase 2 physical audit remain open. No power-loss, remote ownership or distributed
readiness claim; no push, cloud, POM, workflow, legacy format or frozen limit change.
