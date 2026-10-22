# V5.3 — controlled cluster operations

**Status:** local development branch, started 2026-10-21. Phases 0 and 1 are locally closed;
no V5.3 runtime, release, protected CI or cloud acceptance is claimed.

The operator authorized development on `feat/v53-cluster-operations` while V5.2
cloud qualification continues, with local commits and no push. The branch starts
at `73f3bd5c21c97eee564397ab11af7b66bc1b13a3`. V5.2 is still an unpublished
development predecessor; its eventual published artifacts are not yet pinned.

## Frozen local contract

- [Phase 0 contract](PHASE_0_CONTRACT.md) and [protocol](MEMBERSHIP_PROTOCOL.md)
- [API/bytes/compatibility](API_FORMAT_AND_COMPATIBILITY.md) and [resource limits](RESOURCE_AND_LIFETIME_LIMITS.md)
- [Acceptance register](ACCEPTANCE_REGISTER.md), [checklist](PHASE_0_CHECKLIST.md), [Phase 1 entry](PHASE_1_ENTRY_PLAN.md)

[Closure audit and evidence](PHASE_0_CLOSURE_AUDIT.md) record 198 tests and all nine
research matrices on the final script bytes. The [Phase 1 closure audit](PHASE_1_CLOSURE_AUDIT.md)
records current compatibility, byte, source-selection and complete causal-model
qualification. The new membership runtime remains disabled. [Phase 2 storage](PHASE_2_ENTRY_PLAN.md)
is open, with [private durable allocation and exclusive ownership](PHASE_2_STORAGE_FOUNDATION.md)
and the [promise/original-basis metadata journal](PHASE_2_GRANT_JOURNAL.md), now with
[physical original-source retention](PHASE_2_BASIS_SOURCES.md) and
[current local generation capture](PHASE_2_CURRENT_GENERATION.md), followed by
[durable original selection](PHASE_2_DURABLE_SELECTION.md).
[Selected local installation](PHASE_2_GENERATION_INSTALL.md) now preserves the original
source decision across generation/selector writes and interrupted recovery. Its
174-case local process gate passes. The [adoption fence](PHASE_2_ADOPTION_FENCE.md)
now passes 66 cases. [Integrated local adoption](PHASE_2_ADOPTION_INSTALL.md) passes
234 cases with forced prefix/selector recovery and obsolete-view refusal.
[One retained governing floor](PHASE_2_GOVERNING_FLOOR.md) now passes 315 cases,
with complete original copies and old/joint/new majorities. [Inactive-generation
retirement](PHASE_2_RETIREMENT.md) passes 549 cases, including interrupted deletion
and recovery. [Exact journal compaction](PHASE_2_JOURNAL_ROTATION.md) passes
135 cases while preserving all retained sources. [Old floor-copy release](PHASE_2_FLOOR_RELEASE.md)
passes 261 cases and returns its reservations before another complete floor. Actual
vote/application persistence and original-source lifetime progress remain open.
[Automatic journal backpressure](PHASE_2_JOURNAL_BACKPRESSURE.md) now attempts one
safe compaction before refusing an exhausted admission. The [pre-cloud checklist](PRE_CLOUD_CLOSURE_CHECKLIST.md) tracks the
expanded continuous local development scope.

The [Phase 2 closure checklist](PHASE_2_CLOSURE_CHECKLIST.md) tracks integrated
storage work and the final requirement-by-requirement audit.

## Historical research in order

1. [Local development and integration rules](LOCAL_DEVELOPMENT_SEQUENCE.md)
2. [Phase 0 entry and actual source audit](PHASE_0_ENTRY_PLAN.md)
3. [Membership design decisions and open protocol obligations](MEMBERSHIP_DESIGN.md)
4. [Durable ballot research and handoff boundary](BALLOT_AND_HANDOFF_RESEARCH.md)
5. [Predecessor-certified transition research](TRANSITION_CHAIN_RESEARCH.md)
6. [Checkpoint, floor and retention research](RECOVERY_AND_RETENTION_RESEARCH.md)
7. [Global promise, recovery selection and activation](GLOBAL_PROMISE_AND_ACTIVATION_RESEARCH.md)
8. [Authority retention and learner identity](AUTHORITY_AND_LEARNER_RESEARCH.md)
9. [Queryable operations and maintenance](OPERATION_AND_MAINTENANCE.md)
10. [Certified operations and learner admission](INTEGRATED_PROTOCOL_RESEARCH.md)
11. [Stable rounds and complete catalog capsules](STEADY_ROUNDS_AND_CATALOG.md)
12. [Phase 0 closure worklist](PHASE_0_CLOSURE_PLAN.md)
13. [Independent model and later evidence requirements](TESTING_AND_EVIDENCE.md)
14. [Development status](DEVELOPMENT_STATUS.md)

The accepted [V5 charter](../DEVELOPMENT_CHARTER.md) and the V5.3 section of the
[development addendum](../NEXT_DEVELOPMENT_ADDENDUM.md#v53-controlled-operations)
define the direction: non-voting catch-up, controlled membership, restartable
operations and same-version maintenance. Search semantics remain inherited from
published V4.4; automatic leadership and explicit read guarantees remain inherited
from their version-specific contracts. This directory does not amend V5.2 evidence.

## Run the lightweight local research checks

```bash
python3 -m unittest discover -s scripts/v53 -t . -p 'test_*.py'
python3 -m scripts.v53.membership_model \
  --output "target/v53-membership-model/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.ballot_research \
  --output "target/v53-ballot-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.transition_research \
  --output "target/v53-transition-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.recovery_research \
  --output "target/v53-recovery-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.activation_research \
  --output "target/v53-activation-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.admission_research \
  --output "target/v53-admission-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.operation_research \
  --output "target/v53-operation-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
python3 -m scripts.v53.integrated_research \
  --output "target/v53-integrated-research/run-$(date -u +%Y%m%dT%H%M%SZ)"
```

The additional composition driver is `python3 -m scripts.v53.continuity_research --output <new-directory>`.

Run from the repository root. The output directory must be new. These commands
need no Maven build, sudo, network, cloud credentials or running GSE processes.
They check the declared finite model only. See the retained
[research receipt](membership-research.json) and [coverage limits](TESTING_AND_EVIDENCE.md).
