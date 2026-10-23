# Retained offline plan and coordinator ownership

Status: private exact-plan persistence locally qualified. Public bootstrap remains
disabled. This is a durable **plan**, not PREPARED/COMMITTED replica admission.
Phase 2 remains **OPEN**.

## Exact projection container

`MembershipBootstrapPlanData` binds the initial ROOT and GENESIS frames, the full
application image length/hash, captured application/core/source/path descriptors,
source/operation budgets, and every target's exact initial file/directory inventory.
Decoding reconstructs the initial capsule and all target payloads before comparing
the recorded inventories. It checks original root/genesis/configuration/history,
source descriptors, disjoint path bindings and completion capacity. The public
plan summary hashes the entire container; it is not merely a request digest.
The separately stored image is never embedded repeatedly in JSON.

GSBP is a private container, separate from the unchanged 24 GSER and 21 GSRP kinds:

| Field | Encoding |
| --- | --- |
| Magic | four bytes `GSBP` |
| Version | unsigned big-endian shorts 1, 3 |
| Kind / flags | unsigned big-endian shorts 1 (PLAN), 0 |
| Body length | four bytes; exact remaining bytes after the 48-byte header |
| Digest | SHA-256 of the first 16 header bytes followed by the body |
| Body | exact canonical ASCII JSON, schema `gse-v53-bootstrap-plan/1.3` |
| Maximum | 2 MiB including header |

Original frames use canonical base64 with their own original format bounds. The
application remains one bounded 64 MiB image. The plan budget includes two plan
copies, this image and all projected target payload bytes. Preparing replicas and
publishing decisions/receipts/seals must reserve their additional overhead before
those transactions are enabled. Metadata decoding does not replace typed codec
verification or turn the summary into storage authority.

## Exclusive plan owner

`MembershipBootstrapPlanFiles` creates an absent operation directory and exclusively
locks its forced empty `operation.lock`. It writes the exact image, forces it and
its parent, then writes and forces `plan.next.gsbp`. Before the plan is returned it
re-forces the image, atomically renames the complete plan to `plan.gsbp`, forces the
active file and directory, and rechecks all owner/file/parent identities. Replica
and materialization targets remain absent throughout this plan-only component.

The only retained files are the lock, `application.image`, active plan and optional
candidate. Open requires the reviewed exact summary and a complete original active
or candidate plan with the exact image. It never fills a missing suffix from new
arguments, falls back from a corrupt active plan to a good candidate, or allocates
a different history. A complete candidate can be re-forced and published; a
redundant byte-identical candidate can be removed only after the active plan and
image have been forced. Source/path descriptors remain original, even when evidence
is later copied to another location for analysis.

A crash before a complete plan may leave an empty directory, missing lock/image,
or partial image/plan. Those bytes are retained and refused without repair. This
is an explicit pre-admission failure, not successful resumable initialization.
There is no target authority or returned plan at those boundaries. A later public
planner must report it and require operator inspection instead of silently changing
the history or recursively deleting the directory.

## Qualification

[Source/build/raw index](phase2-evidence/bootstrap-plan.json) records 42 passing Java
tests: eight plan tests plus seed, application-image, declaration and version-boundary
regressions. Pure plan tests cover all 3/4/5 sizes and EMPTY/verified backup, exact
request/configuration binding, hostile framing and rechecksummed inventory changes,
source/image/budget mismatch, exclusive ownership, byte-identical inode replacement,
copied coordinator paths, absent/corrupt originals and redundant candidate cleanup.

The integrated three-voter plan producer retains **20 injected interruption cases**.
Nine pre-plan boundaries refuse without changing bytes; eleven complete-plan
boundaries are interrupted a second time during image reseal, then complete with
the original exact plan/history. Raw original plan/image, both interrupted states,
final states and force traces remain retained. Independent Python rebuilds each
target inventory and predicts every file prefix, publication and recovery force
sequence. Eleven exact-reason negatives, relocated replay and normal/optimized
Python agree. These are IOException boundaries, not fresh-process deaths or power
loss. Typed image semantics remain Java checks; the coordinator has committed no
replica, receipt, local seal or membership operation.

```bash
python3 -m scripts.v53.bootstrap_plan_evidence <v53BootstrapPlanEvidence-directory>
python3 -O -m scripts.v53.bootstrap_plan_evidence <v53BootstrapPlanEvidence-directory>
```

## Remaining offline integration

Connect durable once-only random history allocation and the public planner to this
original plan, then implement complete preparation and the four fixed BOOTSTRAP
decisions, exact global receipt and local seals. The existing frozen BOOTSTRAP kind
can describe decisions; it does not itself provide the additional private plan,
preparation or seal representation. Relative target paths in that record must bind
to the original absolute path descriptors, not be interpreted from the process cwd.

Complete-target open must verify its own original admission seal before using the
private storage owner. Repeated process-crash recovery, exact original-first
physical evidence, complete operation/local resource accounting and public entry
qualification remain pending. The seed and plan components do not close these
obligations or the separate transferred-context lifetime work.
