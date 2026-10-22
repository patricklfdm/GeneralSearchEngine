# V5.3 — controlled cluster operations

**Status:** local development branch, started 2026-10-21. Phase 0 is open;
no V5.3 runtime, release, protected CI or cloud acceptance is claimed.

The operator authorized development on `feat/v53-cluster-operations` while V5.2
cloud qualification continues, with local commits and no push. The branch starts
at `73f3bd5c21c97eee564397ab11af7b66bc1b13a3`. V5.2 is still an unpublished
development predecessor; its eventual published artifacts are not yet pinned.

## Read in order

1. [Local development and integration rules](LOCAL_DEVELOPMENT_SEQUENCE.md)
2. [Phase 0 entry and actual source audit](PHASE_0_ENTRY_PLAN.md)
3. [Membership design decisions and open protocol obligations](MEMBERSHIP_DESIGN.md)
4. [Durable ballot research and handoff boundary](BALLOT_AND_HANDOFF_RESEARCH.md)
5. [Predecessor-certified transition research](TRANSITION_CHAIN_RESEARCH.md)
6. [Checkpoint, floor and retention research](RECOVERY_AND_RETENTION_RESEARCH.md)
7. [Independent model and later evidence requirements](TESTING_AND_EVIDENCE.md)
8. [Development status](DEVELOPMENT_STATUS.md)

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
```

Run from the repository root. The output directory must be new. These commands
need no Maven build, sudo, network, cloud credentials or running GSE processes.
They check the declared finite model only. See the retained
[research receipt](membership-research.json) and [coverage limits](TESTING_AND_EVIDENCE.md).
