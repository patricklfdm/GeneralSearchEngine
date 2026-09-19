# Moving from V4.4 to V5.0

**Status:** `5.0.0` is published and independently verified.
Published `4.4.0` remains the prior stable release and compatibility reference.

## Existing single-node applications

Keep using `SearchEngine.builder(...).build()` for memory-only operation and
`buildDurable()` for local durability. V5 does not change either mode into a
replicated service. Core and the optional annotation processor move together to
`5.0.0`; V1–V5 consumer fixtures and the published API comparisons remain gates.
The V4 live formats `(1,0)`, `(1,1)` and `(1,2)` retain their existing authority and
explicit format-selection rules. See [API compatibility](API_COMPATIBILITY.md).

## Enable replication explicitly

Add the optional artifact alongside the same-version core:

```xml
<dependency>
  <groupId>io.github.patricklfdm</groupId>
  <artifactId>general-search-engine-replication</artifactId>
  <version>5.0.0</version>
</dependency>
```

This coordinate is available from Maven Central.
Core does not depend on replication; the annotation processor remains optional.

1. Define one group identity, exactly three fixed voter identities/endpoints, one
   configured leader, codec/schema identities and bounded storage/transport limits.
   Keep replication on a trusted private network; the protocol is not a public
   authenticated service endpoint.
2. Stop the target volumes and use `ReplicationStorageOperations.planBootstrap`
   followed by `applyBootstrap`. Choose empty genesis or a portable V4 application
   backup. Review the plan and preserve the operation directory for explicit resume
   or cleanup. The result seals public replicated format 1.1.
3. Place each sealed replica volume with its corresponding member and configuration.
   `ReplicatedSearchEngines.builder(applicationBuilder, groupConfig).build()` returns
   a stopped handle. It performs no storage or network startup.
4. Start all three handles. On the configured leader, call `activateConfiguredLeader()`
   and await completion before issuing application work. Startup alone does not
   activate the group. Followers reject public application calls.
5. Await asynchronous mutation results. A successful mutation includes durable
   quorum entry and commit proof before leader application/publication. An uncertain
   failure or cancelled future is not evidence that an operation never committed;
   reconcile application state before retrying a non-idempotent request.
6. Use explicit `catchUp(node)` for recovery. Leader reconstruction after replacement
   requires the separate `reconstructConfiguredLeader()` operation and both surviving
   voter identities. V5.0 has no automatic election or promotion.

The independently compiled [V5 configuration fixture](../../../compatibility/v5-style-consumer/src/main/java/fixture/V5StyleConsumer.java)
and [offline API fixture](../../../compatibility/v5-style-consumer/src/main/java/fixture/V5AdmissionConsumer.java)
show the exact typed declarations. They are compile fixtures, not a deployment
script. [Offline authority](PUBLIC_ADMISSION_OFFLINE_AUTHORITY.md) and
[public runtime](PUBLIC_ADMISSION_RUNTIME.md) define resume, cleanup and lifecycle
outcomes in detail.

## Maintenance and recovery boundaries

| Operation | Meaning |
| --- | --- |
| `currentSequence()` | Application sequence; it is not the replicated log index |
| Leader reads | Published applied view; quorum loss may leave a readable earlier view |
| `checkpoint()` | Local committed-state maintenance; creates no application entry or recovery-floor advance |
| `backup(...)` | Portable committed V4 application state; cannot repair or join an existing replica group |
| Replica snapshot / catch-up | Group-bound recovery authority, including log/commit identity |
| Offline replacement | A replacement starts non-voting and must complete the documented recovery path |

Never point a replicated engine at a V4 live directory or use V4 mutation tools on
replica authority. In-place conversion, mixed V4/V5 groups, mixed V5 protocol
versions, rolling upgrades and replica downgrade are unsupported. Importing a
portable application backup creates a new group; it does not transfer old group
membership or commit authority. Backup targets must be outside owned replica storage.

## Evidence scope

The [registered cloud baseline](PHASE_6_BASELINE.md) covers three canonical
repetitions, experiment and failure-drill at the retained snapshot source. Its
10/20 requests-per-second workloads establish the documented behavior and resource
bounds; they do not establish maximum throughput, a latency SLA or automatic failover.
Release preparation changed coordinates, packaging and release tooling, preserving
that measured runtime source. Published JAR hashes match the frozen inventory in the
[candidate manifest](candidate-artifacts.sha256).
