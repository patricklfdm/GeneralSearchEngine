# V6 architecture preview: partitioned distributed search

**Status:** PROPOSED, revision 0.1, 2026-09-19. Research and design only.

**Review base:** `066a04602f7116a0386c645ddfcf4c2e3d41312a`.

**Prerequisite:** an accepted mature V5 replicated-group handoff, proposed at V5.4.
No V5.4 release or exact baseline exists in this proposal; pin it only when available.

## 1. Objective and major-version boundary

Compose independently replicated shards into one logical search dataset. Define
routing, supported query transmission, aggregation, consistency, failure behavior
and resource bounds, then measure how capacity and query performance change with
physical resources. This is a distributed-search line, not a general-purpose big-data
platform, stream processor, multi-writer store or analytics SQL engine.

The [accepted V5 charter](../v5x/DEVELOPMENT_CHARTER.md) explicitly excludes sharding
and distributed query. This preview does not amend that boundary. V6 should use
reviewed public group capabilities rather than importing private replica classes
or maintaining a second election implementation.

A conceptual decomposition is:

```text
Application
    |
Distributed access layer
    |-- versioned routing and bounded write dispatch
    |-- bounded query coordination and result aggregation
    |
    |-- logical shard A --> V5 replication group A
    |-- logical shard B --> V5 replication group B
    `-- logical shard C --> V5 replication group C
```

Packaging is a Phase 0 decision. Recommended posture: an optional distributed API
/module retaining embedded use, without adding mandatory networking to the core or
processor. Do not force every existing single-node method into a remote abstraction.
A separately operated daemon, service discovery platform, public-network security
surface and Kubernetes operator are not implicit V6.0 deliverables.

## 2. Proposed release decomposition

| Planning label | Boundary | Principal exit question |
| --- | --- | --- |
| V6.0 | Fixed logical shards, static placement, versioned routing, single-shard writes and a bounded query subset | Can the dataset be partitioned and queried correctly without silently changing existing guarantees? |
| V6.1 | Distributed relevance, query-view management and stable pagination | Are ranking and pages consistent with the precisely defined global query semantics? |
| V6.2 | Controlled shard relocation and explicit placement transitions | Can ownership move without lost writes, dual ownership or unsafe source cleanup? |
| V6.3 | Capacity, skew, recovery and long-run hardening | What supported scale and resource envelope is actually demonstrated? |

These labels may change through review. Each release requires its own contract and
evidence plan. They are not permission to implement all four in one branch.

## 3. V6.0: deliberately constrained first distributed boundary

### 3.1 Stable identities and static placement

Separate document identity, logical shard identity, replication-group identity,
physical host and placement-map version. A deterministic versioned key-partition
function maps keys to a fixed set of logical shards; an explicit map places each
shard on its replication group. Do not partition by the current machine count.

Initially keep placement static during normal operation. Freeze routing-key encoding,
hash/version, key equality and ownership. Reject stale or incompatible routing maps
at the destination as well as the coordinator. Detect duplicate shard ownership,
missing groups, wrong schema/analyzer identity and incorrect target shard. A client
hint is not an ownership proof.

Partition-key changes and global identity constraints need explicit semantics.
Recommended first boundary: routing key is immutable for ordinary update; reject
cross-shard moves rather than silently performing a non-atomic delete/add.

A static map does not need a new general-purpose consensus service, but it still
needs a defined authority, distribution and activation procedure. Dynamic metadata
and online placement changes remain outside the static V6.0 boundary.

### 3.2 Mutation and schema guarantees

Preserve single-key and single-shard batch semantics through the underlying V5
group. An atomic batch spanning shards must be rejected before any dispatch or
mutation. A future non-atomic distributed bulk API must be separately named and
return explicit per-item/per-shard outcomes; a single ambiguous Future must not
pretend to provide cross-shard atomicity. No cross-shard transaction in V6.0.

Define bounded dispatch, partial transport failure, cancellation and response-loss
classification. Routing retries after possible dispatch must not silently duplicate
mutations. Any deduplication mechanism must have a reviewed durable scope and
retention model, not just a coordinator-local cache.

Require one admitted schema/analyzer/configuration identity for the query surface.
Dynamic per-group index operations inherited from V5 are not automatically an atomic
whole-dataset schema operation. Recommended initial boundary: freeze the distributed
schema and index definitions; allow only explicitly offline/coordinated changes or
reject unsupported global changes. Do not report full schema success while some
shards have different interpretation.

### 3.3 Transmittable queries, not arbitrary lambdas

The inspected [Query API](https://github.com/patricklfdm/GeneralSearchEngine/blob/066a04602f7116a0386c645ddfcf4c2e3d41312a/src/main/java/io/github/patricklfdm/generalsearch/query/Query.java)
is a Java functional interface. Its ability to accept an arbitrary local predicate
must not be confused with a transport contract.

Design a bounded, versioned query AST with canonical field identities and typed
literal encodings. Specify nulls, numeric/overflow rules, string comparison/collation,
Boolean semantics, analyzer identity, operator limits and unsupported-node errors.
Freeze request/result formats and exhaustive support tables before implementation.
Do not serialize arbitrary Java objects, lambdas, comparators or user code for remote
execution. Keep unsupported local customization usable locally, not silently remote.

Start with a documented structured-filter subset and deterministic typed field/key
sorting. Enforce maximum results, K, AST depth, fan-out, bytes and execution budgets.
Unbounded 'return all matches' methods need their own streaming/resource contract;
they are not implicit distributed compatibility requirements.

### 3.4 Complete results by default

All required shards must succeed for a response labelled complete. In V6.0, a missing,
timed-out or incompatible shard should fail the query instead of returning a normal
success with hidden omissions. Reject duplicate shard responses and map mismatches.
Use one end-to-end deadline and bounded downstream work; cancellation must release
pins, queues and streams according to a defined contract.

If partial results are added later, require explicit opt-in and return shard coverage,
failures and affected count/ranking semantics. 'Some hits arrived' is not a complete
result. A retried query must not accidentally merge different view generations.

### 3.5 Ranking and view scope

Recommended V6.0 boundary: supported filtering plus deterministic non-relevance sort
and bounded top-K under a single global total order. Relevance-ranked distributed
requests remain explicitly unsupported until their V6.1 contract exists. Reject them
rather than substituting shard-local BM25 and claiming the original semantics.

At minimum, identify the committed view used by each shard during a query. A vector
of individually valid shard views is not automatically a globally simultaneous or
causally consistent transaction snapshot. State the actual guarantee and do not claim
cross-shard snapshot isolation without the necessary coordination protocol.

## 4. V6.1: global search semantics

### 4.1 Ranking and query preparation

Define the exact global scoring semantics, corpus/statistics scope, document lengths,
term frequencies, field weights, precision and deterministic tie-break. Elastic's
[search API](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-search)
distinguishes shard-local from global term/document-frequency search modes. That is
a useful reference for the trade-off, not evidence that GSE currently supports either.

For an exact global-statistics design, pin the required shard views, derive statistics
from those same views, bind a statistics identity to the request, run each shard with
the same interpretation, then merge using the same total ordering. Define global
query rewriting as well as scoring: fuzzy expansion, term-selection caps and similar
rewrites cannot silently vary by shard if monolithic-equivalent semantics are claimed.

Do not retrieve local top-K under local scores and only then rescore the survivors
with global statistics. Necessary globally high-ranking documents may already have
been omitted. Where a local top-K merge is claimed exact, state and test its
assumptions: disjoint ownership, identical ranking/order and no unaccounted global
selection, grouping or deduplication constraints.

### 4.2 Pagination, explanations and retained views

A cursor should bind query/sort identity, schema/analyzer identity, placement version,
shard-view identities and continuation state. Freeze expiry, size and pin budgets,
crash/restart behavior and errors when views are no longer available. Never silently
repin a newer corpus and continue the same cursor. Deterministic ordering must include
a stable globally unique tie-break; incidental replica-local row numbers are not enough.

Define whether views remain usable across leader changes, and when an explicit expired
or unavailable-cursor failure is required. Distinguish stable pagination over a
pinned view vector from a globally simultaneous snapshot.

Explanations, highlighting, counts and query rewrites must refer to the same chosen
views and scoring context. Approximation is a separately specified capability, never
an undocumented optimization of an exact request.

## 5. V6.2: controlled relocation before fully online resharding

Start by moving existing logical shards. Do not initially combine relocation with
shard split/merge, a new key-partitioning scheme and unrestricted schema migration.
Define the authoritative placement state machine and a durable operation identity.
One active write owner must remain unambiguous throughout the transition.

A candidate controlled procedure is:

```text
Prepare and validate target
  -> transfer a bound state image
  -> catch up to the required committed position
  -> establish a write handoff barrier
  -> publish the new ownership/placement version
  -> verify the target and stale-route rejection
  -> reclaim the old state only after its safety conditions hold
```

This is an outline, not a proven migration protocol. The V6.2 contract must identify
linearization points, acknowledgments, ownership fencing, target/source loss, repeated
requests, interrupted stages, rollback versus forward recovery, query-view handling,
retention and abandoned-operation cleanup. Allow a documented short write pause first
rather than promising seamless online migration without a protocol argument.

Physical relocation of one group's replicas and logical transfer of shard ownership
between groups are different operations. Choose which is supported and how V5
membership semantics are reused; do not treat a replica snapshot as sufficient
permission to create a second writable owner of the same logical shard.

## 6. V6.3: measurable capacity and operating envelope

Use a pinned mature single-shard V5 replicated group as the primary topology-matched
control. Keep V4.4 as a search/storage truth reference where appropriate, but do not
attribute the entire difference from an unreplicated baseline to sharding overhead.

| Experiment | Controlled variable | What changes | Claim it can support |
| --- | --- | --- | --- |
| Fixed dataset, more resources | Corpus and workload meaning | Physical resources and placement | Strong-scaling behavior under that workload |
| Proportional dataset and resources | Per-resource data/load definition | Corpus and physical resources | Weak-scaling behavior within measured bounds |
| Fixed resources, varying shard count | Hosts, total CPU/memory/disk and dataset | Logical organization | Sharding overhead/benefit, not horizontal node scaling |

Freeze physical topology, fault domains, document-size distribution, indexed fields,
selectivity, routing skew, read/write mix, warm/cold state, repetitions, offered load
and error accounting. Report p50/p95/p99, completed throughput, queueing, coordinator
bytes/CPU/heap, replica resources, recovery duration and data/index sizes. Tail latency
must not exclude failed or timed-out requests from the accompanying outcome account.

Include hot shards, uneven corpus distribution, scatter/gather queries, shard-local
queries, expensive filters, concurrent ingestion and recovery. A coordinator may become
the bottleneck even if shard CPU is low. Use rate sweeps to locate sustainable load;
a fixed offered-rate success is not a maximum-throughput result.

Current V5.0 [cloud evidence](../v5x/v5.0/PHASE_6_CANONICAL_REVIEW.md) uses 4096
documents, controlled 10/20 calls per second, three concurrent VMs in one zone and
24 vCPU/450 GiB peak disks. Those historical measurements are neither a V6 target nor
current quota authorization. Plan fresh capacity/cost/failure-domain checks. Running
more shard processes on the same three machines is useful functional evidence but
does not demonstrate gains from more physical machines. Avoid co-locating two voting
replicas of the same shard in a claimed independent-host fault topology.

Do not preclaim million-document or out-of-core support. Record per-shard working-set,
index amplification, snapshot/recovery peaks and measured capacity. If each shard
still requires its working set in memory, more shards do not eliminate that limit;
a disk-backed index redesign is a separate architectural axis.

## 7. Correctness oracle and entry checklist

For fixed/pinned views, form an independent union oracle using the exact admitted
partitioning, query interpretation, global statistics and comparator. Compare complete
results or a well-defined digest plus ordering/count/ranking checks. A concurrently
changing monolithic snapshot is not automatically equivalent to an arbitrary vector
of shard views; construct the oracle for the promised semantics.

Add counterexamples for wrong routing, duplicate ownership/responses, missing shards,
partial batches, stale maps, divergent analyzers, local/global ranking disagreement,
invalid cursors and handoff interruption. Separate correctness evidence from scale
measurements and bind every baseline to its exact source and artifacts.

Before V6 production implementation, require an accepted V5 handoff, a V6 charter,
Phase 0 decisions on the above boundaries, proposed public API/format inventories,
an independent-model and public-consumer plan, finite resource budgets and a reviewed
Phase 1 entry. Before each paid experiment, require fresh authorization and preflight.

The immediate next engineering task remains [V5.1 Phase 0](../v5x/v5.1/PHASE_0_ENTRY_PLAN.md).
This preview reserves design questions early; it does not authorize parallel V6 code.
