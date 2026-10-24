# Phase 2: public offline bootstrap entry

`MembershipStorageOperations` connects its four existing bootstrap declarations to
the typed coordinator: `planBootstrap`, `applyBootstrap`, `resumeBootstrap` and
`readBootstrapResult`. Signatures and constructors stay unchanged. Learner methods
and the online membership engine remain disabled; an offline committed group is
not evidence of an active leader, quorum or public read/write service.

Planning captures the builder configuration once, verifies the real typed source,
persists one random history and exact plan, and leaves voter directories absent.
The fixed projection and complete original decision/admission bytes share the
existing operation budget. Planning is persistent work, not a pure constructor.
An incomplete plan is never replaced with a new history during recovery.

Apply and resume use the same original transaction qualified by the
[typed repeated-process matrix](PHASE_2_BOOTSTRAP_TYPED_PROCESS.md). Only resume
may finish remaining seals around already completed live voters; it neither
reopens their locks nor resets their mutable stores. After COMMITTING, exact
request/configuration still bind recovery, while the original backup/projection
need no longer be present. The retained plan/image/decision/admissions remain
mandatory. Result inspection is read-only and verifies the original completed
bootstrap, not current runtime readiness or mutable-store integrity.

## Failure contract

Null arguments are rejected before configuration capture or I/O. Exact metadata
and request validation use `IllegalArgumentException`; classified filesystem,
core-backup and capacity failures retain the existing offline
`ReplicationException` translation, including the original cause. These methods
do not return an online `MembershipOperationId` or a NOT_SUBMITTED assertion.
After an interrupted apply, inspect the original operation and explicitly resume
that exact plan; failure alone does not establish that no decision was written.
No automatic cleanup or hidden retry is added.

## Local qualification

The shared original-result suite enters through the public plan/apply/resume/read
methods for all six size/source profiles. It opens 24 actual admitted voters,
forces grants and counter progress, checks results while their locks remain live,
and retains original and progressed physical evidence. Independent replay checks
the exact original result and bytes, rejects altered authority and scope, and
replays a relocated copy. The private profile remains separately supported.

Additional public recovery tests complete exact PREPARED and COMMITTING
interruptions for all six profiles, reject changed requests without mutating
authority, and recover without the removed source after COMMITTING. Nulls,
missing results and insufficient initial budget are refused without fabricated
authority. Existing declaration tests continue to require disabled learner and
online operations. Precise results and source/build hashes are in the
[local evidence index](phase2-evidence/bootstrap-public.json).

The public adapter tests use exception interruption; child-process death coverage
belongs to the unchanged coordinator implementation qualified in the preceding
batch. No claim of independent codec semantics, power-loss durability or Phase 2
closure is made. Context transfer, maximal/cross-view lifetime and the final
storage requirement audit remain open.
