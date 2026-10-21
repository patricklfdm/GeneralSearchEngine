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
4. [Independent model and later evidence requirements](TESTING_AND_EVIDENCE.md)
5. [Development status](DEVELOPMENT_STATUS.md)

The accepted [V5 charter](../DEVELOPMENT_CHARTER.md) and the V5.3 section of the
[development addendum](../NEXT_DEVELOPMENT_ADDENDUM.md#v53-controlled-operations)
define the direction: non-voting catch-up, controlled membership, restartable
operations and same-version maintenance. Search semantics remain inherited from
published V4.4; automatic leadership and explicit read guarantees remain inherited
from their version-specific contracts. This directory does not amend V5.2 evidence.
