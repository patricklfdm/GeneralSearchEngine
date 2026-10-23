# Phase 2 — admission publication across repeated process death

Status: **private admission-file process qualification; Phase 2 OPEN**.
The production implementation is unchanged from the
[admission-file transaction](PHASE_2_BOOTSTRAP_ADMISSION_FILES.md).

A dedicated worker opens the actual retained plan and initial application image,
then uses the explicit admission-file transaction profile. Each of the **21**
COMMITTED/admission/first-seal boundaries is interrupted by both `Runtime.halt`
and external SIGKILL. A second fresh process resumes the same original decision
and dies again at `BOOTSTRAP_ADMISSION_0_FORCED`. A third fresh process completes.
There are **42 cases / 126 workers**, with no new history, retry ballot or plan
regeneration. Parent tests wait for the child's flushed kill marker before SIGKILL
and check exit status, stderr and complete final local metadata.

The independent original-first Python model derives exact preparation, decision,
receipt, admission and seal bytes from retained original plan/image. It checks all
three event traces, three physical snapshots, all returned result bindings and the
complete receipt scope. **15 exact evidence negatives** reject damaged originals,
missing/extra or altered crash inventories, early admission, lost admission on a
different target, changed execution/result traces, stderr, false process/typed
claims and linked authority. Normal/optimized Python and relocated replay agree.

[Source/build evidence](phase2-evidence/bootstrap-admission-process.json) retains
all raw files, inputs, compiled outputs and test/replay logs. Earlier component
receipts remain unchanged. These new results only cover **three EMPTY initial
voters** and explicit no-op typed callbacks; in-process all-size/backup tests are
separate evidence. They do not establish all-size typed coordinator process safety,
complete-store admission, network behavior or power-loss semantics.

Next: connect immutable local admission to exclusive store opening and original
coordinator completion budgets/rechecks; qualify typed callbacks and supported
source/size profiles. Result/resume inspection after legitimate runtime changes
must preserve mutable state and never restore genesis. The remaining cross-view,
context-transfer and maximal lifetime audit is still OPEN. No public bootstrap,
learner eligibility, workflow, POM, frozen catalog or paid-cloud change.
