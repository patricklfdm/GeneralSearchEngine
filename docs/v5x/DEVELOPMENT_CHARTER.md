# GeneralSearchEngine V5 development charter

- **Status:** Accepted governing charter (protected PR #145)
- **Reference release:** published GeneralSearchEngine `4.4.0`
- **V5 boundary:** replicated single-shard search
- **V5.0 goal:** correct replication under one configured leader

## Purpose

V5 lifts durable authority from one local process to one replicated group while
preserving the published V4.4 query and mutation semantics. The V5 line targets one
logical dataset with one authoritative mutation order, quorum-backed commit, safe
leadership, replica recovery, explicit read consistency and operable membership.

V5 is not the sharding line. It does not partition the corpus or perform distributed
query fan-out. Those decisions remain outside V5.

## Frozen predecessor

Published `4.4.0` remains the immutable compatibility and failure-classification
oracle. V5 must inherit:

- immutable snapshots, lock-free readers and one ordered writer;
- atomic single and bulk mutation visibility;
- V3.4 retrieval, ranking, pagination, highlighting and explanation semantics;
- force-before-success durability and indeterminate incomplete operations;
- fail-closed recovery, checksummed storage and atomic checkpoint publication;
- backup, restore, inspection, migration and derived-state separation; and
- bounded resource, cleanup and exclusive-ownership behavior.

V5 must not silently reinterpret `gse-durable` or `gse-backup` bytes as replicated
cluster authority.

## Governing principles

1. The valid committed replicated history is the only cluster authority.
2. Safety wins over availability whenever leadership, quorum or history is uncertain.
3. One authoritative mutation order remains; V5 has no multi-writer merge model.
4. Search observes only applied committed state.
5. Replication changes topology and latency, not frozen V4.4 search truth.
6. Storage and wire formats have explicit families, versions and rejection rules.
7. The V5.0 core is a configured-leader restriction of the V5.1 consensus model,
   not a temporary replication algorithm that V5.1 must replace.
8. Structured trace, deterministic network faults, separate-process crash testing,
   fake cloud and durable multi-node cloud lanes are architecture from Phase 1.
9. Numeric bounds are finite and fail closed; no slow peer may create unbounded
   memory, disk or network growth.
10. Every release claim is bound to exact source, independent evidence and protected
    master.

## Product and packaging boundary

V5 remains an embedded Java library. An application starts one replica node per JVM;
V5.0 does not introduce a separately administered GSE daemon or service discovery.

Replication is an opt-in capability in a new Maven artifact with frozen identity:

```text
io.github.patricklfdm:general-search-engine-replication
```

The artifact depends on `general-search-engine`; the existing core and processor
artifacts must not acquire a mandatory networking dependency. Phase 1 freezes the
exact Java declarations and the production transport dependency before production
replication begins. Test transports remain internal.

## V5.x plan

### V5.0 — replication foundation

V5.0 freezes and implements:

- one replication group and exactly three fixed voters;
- one configured leader identity and two followers;
- quorum-backed durable append and durable commit proof;
- leader activation with persisted epoch promises and stale-incarnation fencing;
- leader-only public reads and writes;
- deterministic document, bulk and index-lifecycle replication;
- restart reconciliation, incremental catch-up and verified snapshot transfer;
- explicit bootstrap from an empty group or a source-preserving V4.4 backup;
- deterministic model, network, process-crash and cloud evidence.

V5.0 is a replication-correctness foundation. It deliberately does not restore
write or public-read availability after permanent leader loss.

### V5.1 — automated leadership

V5.1 adds candidate selection, elections, failure detection, automatic epoch
advancement, old-leader fencing, safe promotion, rejoin and repeated failover. It
extends the V5.0 log, activation and promise model rather than replacing them.

### V5.2 — replica reads

V5.2 adds explicit leader, stale-allowed and at-least-index read contracts. No
follower read may imply stronger consistency than it proves.

### V5.3 — cluster operations

V5.3 adds controlled add/remove/replace operations, membership transitions, rolling
restart and maintenance. Joint-consensus or an equivalently reviewed safe membership
protocol is required before the fixed three-voter manifest may change.

### V5.4 — final replicated hardening

V5.4 closes repeated elections, partitions, slow/corrupt replicas, interrupted
transfer, bounded resources, rolling operations and canonical multi-node evidence,
then hands one mature replicated group to the next architecture line.

Minor-release scope is directional until that minor's own Phase 0 contract is
accepted. A later contract may narrow work but may not weaken an already published
safety guarantee.

## V5.0 phase order

1. **Phase 0 — contract freeze:** authority, identity, commit proof, activation,
   storage layering, API boundary, bootstrap, recovery, protocol, security, failure
   and evidence contracts. Documentation only.
2. **Phase 1 — foundation:** open `5.0.0-SNAPSHOT`; add declaration-only API fixtures,
   independent history model, deterministic transport, structured trace,
   separate-process crash harness, fake-cloud lane and exact resource plan. No
   production replication path.
3. **Phase 2 — replicated storage:** outer storage family, manifest, log, epoch
   promises, durable append, commit ledger and independent inspection.
4. **Phase 3 — leader path:** configured-leader activation, quorum replication,
   durable commit proof, ordered apply/publication and no-quorum rejection.
5. **Phase 4 — recovery:** restart reconciliation, follower replacement, incremental
   catch-up, immutable snapshot install and safe physical compaction.
6. **Phase 5 — hardening:** deterministic network schedules, crashes, corruption,
   pressure, cancellation, close and repeated recovery.
7. **Phase 6 — performance and cloud:** exact V4.4 control, concurrent three-node
   experiment/failure/canonical evidence and resource bounds.
8. **Phase 7 — release candidate:** consumers, compatibility, artifacts, Javadocs,
   reproducibility and final `5.0.0` coordinates.
9. **Phase 8 — publication:** signed tag, Maven Central, GitHub Release and
   post-publication reconciliation.

After Phase 5 acceptance, the [public-admission amendment](v5.0/PUBLIC_ADMISSION_CONTRACT.md)
was accepted in PR #151 as completion work before Phase 6. It preserves this numbering while
specifying the missing public bootstrap/lifecycle boundary, explicit API additions
and a reviewed genesis-format extension. Its [entry plan](v5.0/PUBLIC_ADMISSION_ENTRY_PLAN.md)
separates contract review, implementation and public runtime acceptance.

## Exclusions

V5.0 excludes automatic election, online promotion, public follower reads, dynamic
membership, mixed-version replication, rolling upgrade, in-place V4 conversion,
sharding, distributed query, multi-writer conflict resolution, cross-region claims,
Byzantine faults and hostile-network security claims.

The complete V5 line also excludes sharding, distributed top-K/statistics, vector or
hybrid retrieval and cross-shard cursors unless a future major charter replaces this
boundary.

## Completion definition

V5 is complete only when one single-shard replicated group has quorum durability,
safe automatic leadership, explicit replica reads, controlled membership, bounded
recovery and resources, deterministic fault evidence and canonical concurrent
multi-node cloud evidence. Until then, the project prefers a smaller correct system
to a broader ambiguous one.
