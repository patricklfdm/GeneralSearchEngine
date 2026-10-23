# Phase 2 — private offline bootstrap coordinator

Status: local private orchestration qualified; **Phase 2 remains OPEN**. Public
`MembershipStorageOperations` entries stay disabled until complete-store admission
and result inspection after mutable runtime progress are integrated.

## Planning and original history

`MembershipBootstrapCoordinator` joins source projection, exact plan persistence,
[bounded typed rechecks](PHASE_2_BOOTSTRAP_RECHECK.md) and the all-voter transaction.
For a new operation it selects one random version-4 history, projects all targets,
checks typed source/image agreement and full completion-plus-projection capacity,
then forces the original plan through the existing plan owner. No target is written
during planning.

The retained projection is a sibling of the operation directory, named
`.gse-v53-bootstrap-<SHA-256 of the normalized absolute operation path>.projection`.
Its parent is the operation's already bound original parent. All source/target/path
alias checks still apply. The location is derived from the original plan's operation
path, so later calls cannot choose a different scratch directory. This is derived
application material, not a second ownership authority.

Calling plan again on an existing operation requires its complete original active
plan or complete original candidate and image. It validates the exact request and
performs the real typed check under the coordinator owner before resealing or
promoting the candidate. An incomplete/missing plan is refused with retained bytes;
no replacement history is created. A corrupt active plan never falls back to an
intact candidate. An occupied projection without a plan is preserved for operator
inspection, not silently deleted or adopted into a newly allocated history.

## Apply and recovery

The transaction now supports a plan-aware admission check under its existing owner.
Every apply/resume verifies the exact original request, including budgets and the
captured application configuration. PREPARING and COMMITTING additionally invoke
the real read-only source/projection checker at their existing decision boundaries.
The original transaction force and recovery ordering is unchanged.

Once COMMITTING was forced, recovery completes that original decision without
requiring source or projection files again. It still checks request/configuration
identity and all required retained transaction bytes. This prevents an unavailable
input source from stranding a durable commit, and prevents a changed request from
borrowing the old decision. No new history or prepared authority is reconstructed
from caller arguments.

`readInitialResult` validates only an initial committed store. It is deliberately
private and still requires the original initial payloads and absent materialization
directories; it is not the future public post-runtime result reader.

## Evidence

[Source/build/raw index](phase2-evidence/bootstrap-coordinator.json) records the
coordinator regression plus affected plan/transaction/ownership/declaration gates.
The six successful 3/4/5 × EMPTY/backup cases each use a distinct random history,
repeat plan, interrupt at PREPARED, resume, and read the original result. Four real
typed rechecks per case reuse the original projection with unchanged bytes/inodes.

Additional tests exercise missing/torn/complete plan recovery, refusal before
candidate promotion or the first decision, corrupt-active refusal, occupied scratch,
insufficient budget, and COMMITTING recovery after input files were moved aside.
Wrong request or application configuration still fails without authority changes.
The tests do not delete the unavailable input evidence to manufacture recovery.

Independent replay checks the original source/projection, all final payloads,
preparations, four decisions, receipt and seals, plus six distinct version-4 history
identities. Fourteen evidence mutations, normal/optimized Python and portable replay
are retained; the prior bounded-recheck profile remains separately accepted.

```bash
python3 -m scripts.v53.bootstrap_coordinator_evidence <v53BootstrapCoordinatorEvidence-directory>
```

This is private local qualification. Fresh-process qualification of the fully
integrated typed coordinator, complete local seal admission/accounting, public
post-runtime result reading and the full Phase 2 S/N audit remain open. No protected
CI, cloud, public runtime, release or power-loss claim is made.
