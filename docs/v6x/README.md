# GeneralSearchEngine V6 architecture preview

**Status:** PROPOSED architecture research only, revision 0.1, 2026-09-19.

No V6 development charter, implementation authorization or published capability is
established by this directory. The suggested V6.0-V6.3 labels are planning boundaries,
not approved release commitments.

Read [the architecture preview](ARCHITECTURE_PREVIEW.md) for the proposed partition,
query, consistency and evidence boundaries. The current development entry remains
[V5.1 Phase 0](../v5x/v5.1/PHASE_0_ENTRY_PLAN.md), under the
[accepted V5 charter](../v5x/DEVELOPMENT_CHARTER.md).

The proposed sequence is to complete a mature single-shard replicated group through
V5.4, then compose such groups into a distributed search system. V6 design research
may proceed in parallel, but must not change V5 production APIs or pull sharding
implementation into the V5.x workstream.

The preview intentionally does not promise cross-shard transactions, globally
simultaneous snapshots, arbitrary Java query serialization, out-of-core indexes,
unlimited scale, or a new public-network database service. Those require separate
architecture decisions and evidence.
