# V5.1 Phase 4: public automatic lifecycle

**Status:** Batch A implemented locally on `feat/v5.1-phase4-bootstrap`; protected
acceptance pending. Phase 3 is [accepted](PHASE_3_CHECKLIST.md) at
`263c488fa3d1b0f78ff8a4a4454d7b3b7ff0bfab` (PR #191, CI `35542143840`).
The [checklist](PHASE_4_CHECKLIST.md) separates local qualification from protected acceptance.

The [accepted API contract](API_FORMAT_AND_COMPATIBILITY.md) and
[evidence matrix](TESTING_AND_EVIDENCE.md) govern this phase. The user performs
commit, push and PR. Cloud experiments remain manually triggered by the user.

## Batch A — offline admission

- Enable all six existing `AutomaticReplicationStorageOperations` methods: plan,
  apply, resume, read result, plan cleanup, apply cleanup.
- Import EMPTY and verified V4.4-compatible backups, preserving source bytes,
  sequence, active indexes and document order in a fresh automatic history.
- Force three preparations before one global decision and publish self-contained
  local seals. Keep cleanup limited to exact pre-COMMITTING output.
- Bind complete local materialization settings and parent filesystem identities;
  see the [additive format decision and implementation](PHASE_4_BOOTSTRAP.md).
- Validate through Java regressions, an external consumer compiled against the
  packaged JARs, published V4.4 imports, real halt/SIGKILL and an independent oracle.

## Batch B — runtime façade and reads

Enable the frozen automatic builder only after its admission validates local seal,
application/configuration and ownership without a live bootstrap coordinator.
Implement the complete inherited application and lifecycle façade, status/fencing,
callback ownership and close/cancellation. Each successful strong read requires
a fresh chosen/published NO_OP and one pinned application view, including page,
ranking, highlight and explain variants. Handle all retry outcomes explicitly.

Replace compile-only public-runtime coverage with a real external consumer doing
bootstrap, concurrent start, election, application operations, reads, checkpoint,
backup and close; the controller may not initialize voters or privately activate a leader.
Then run the full Phase 4 evidence matrix and obtain protected acceptance.

Batch A does not claim public-runtime or complete Phase 4 acceptance.
