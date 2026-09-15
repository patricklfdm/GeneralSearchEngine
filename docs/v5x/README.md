# GeneralSearchEngine V5.x development line

- **Status:** Phase 0 accepted; Phase 1 candidate locally validated
- **Stable comparison release:** GeneralSearchEngine `4.4.0`
- **Architecture boundary:** replicated single-shard search

V5.x builds one replicated group over the frozen V4.4 durable/search semantics. V5.0
first establishes correct replication under one configured leader. Later V5 minors
add automated leadership, explicit replica reads, membership operations and final
hardening. Sharding and distributed query are not V5 work.

## Authority map

- [V5 development charter](DEVELOPMENT_CHARTER.md)
- [V5.x roadmap](ROADMAP.md)
- [V5.0 Phase 0 contract](v5.0/PHASE_0_CONTRACT.md)
- [V5.0 architecture and authority](v5.0/ARCHITECTURE_AND_AUTHORITY.md)
- [V5.0 API and compatibility](v5.0/API_COMPATIBILITY.md)
- [V5.0 protocol, recovery and failure contract](v5.0/PROTOCOL_RECOVERY_AND_FAILURES.md)
- [V5.0 Phase 1 transport and frame decision](v5.0/TRANSPORT_AND_FRAMING.md)
- [V5.0 read-only cloud availability record](v5.0/cloud-availability.json)
- [V5.0 testing and evidence plan](v5.0/TESTING_AND_EVIDENCE.md)
- [V5.0 Phase 0 checklist](v5.0/PHASE_0_CHECKLIST.md)
- [V5.0 Phase 1 entry plan](v5.0/PHASE_1_ENTRY_PLAN.md)
- [V5.0 Phase 1 baseline](v5.0/PHASE_1_BASELINE.md)
- [V5.0 Phase 1 checklist](v5.0/PHASE_1_CHECKLIST.md)
- [V5.0 Phase 1 machine-readable plan](v5.0/phase1-plan.json)
- [Published V4.4 to V5 handoff](../v4x/v4.4/V5_HANDOFF.md)

Phase 0 was accepted through protected PR #145 at `105537c8`; exact-master CI run
`34919817954` passed. The Phase 1 candidate opens `5.0.0-SNAPSHOT` and completes the
declaration/model/fixture/crash/fake-cloud foundation locally; protected-master
acceptance remains pending. Production replication and paid cloud execution remain
disabled.
