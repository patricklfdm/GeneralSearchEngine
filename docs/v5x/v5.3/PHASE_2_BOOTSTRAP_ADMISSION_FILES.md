# Phase 2 — admission publication before bootstrap seals

Status: **private admission transaction profile qualified locally; Phase 2 OPEN**.
The original low-level component profile and private coordinator remain distinct;
public bootstrap and complete-store opening remain disabled.

`MembershipBootstrapTransaction.applyAdmitted` uses the original plan, actual
image, target preparation, four decisions and coordinator receipt. It additionally
counts one compact admission file per target in the full completion budget before
any transaction write. After COMMITTED it writes each original admission prefix,
forces the file and parent, then starts publishing local seals. All target admission
files complete before the first seal candidate is created. There is one admission
copy per target, with no extra pending/active pair.

Recovery reuses exact original bytes and all existing owner, inode, filesystem,
receipt and preparation checks. A partial admission can complete only before any
seal exists. Once **any** target has a seal candidate or active seal, every target
must retain its full original admission. Missing or partial bytes on another target
also refuse unchanged. Early/foreign admissions and old component stores that have
seals without admission refuse; this is not an implicit upgrade or repair path.
Repeated resume re-forces original admissions before seals. `readAdmitted` remains
an initial-store inspector and does not support mutable runtime progress.

## Qualification

[Source/build evidence](phase2-evidence/bootstrap-admission-files.json) retains
input hashes, compiled outputs, raw inventories and logs. Six new Java tests cover
all sizes 3/4/5 with EMPTY/verified backup, force ordering and idempotence; insufficient
completion budget before PREPARING; early/foreign/corrupt/missing authority; lost
admission on any target after seals; same-content inode replacement; and **21**
new publication boundaries interrupted again during admission recovery.

The independent model receives an explicit admission profile; default historical
transaction behavior remains unchanged. Original-first replay checks all first
crash, second crash and completed inventories and force events. New-profile and
original-profile physical replays retain separate schemas and exact negative
results. Normal and optimized Python and relocated replay must agree.

The initial suite had one test setup error: its foreign source fixture and one
negative case reused a temporary-directory name. That failure remains retained.
The corrected fixture group and ownership tests are rerun separately; unchanged
related test results and source inputs are recorded rather than hiding that run.

This batch uses thrown I/O interruptions in one JVM. Fresh-process halt/SIGKILL at
these new boundaries, real typed coordinator integration, complete-store immutable
admission verification and the combined MISC completion audit are still required.
The original 48-process transaction matrix predates the admission file and does
not qualify it. No public runtime, learner eligibility, new history fallback,
power-loss, cloud, workflow, POM or frozen-catalog change is claimed.
