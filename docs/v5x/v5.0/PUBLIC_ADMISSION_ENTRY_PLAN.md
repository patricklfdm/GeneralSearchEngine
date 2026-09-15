# V5.0 public-admission entry and acceptance plan

- **Status:** Contract accepted; Step A declarations and byte fixtures under review
- **Branch:** `feat/v5.0-public-admission-foundation`
- **Starting master:** `716f06f6bb04dcbf86e775eb93b4f7f31799739a`
- **Phase 5:** [PR #150](https://github.com/patricklfdm/GeneralSearchEngine/pull/150)
- **Exact-master CI:** [34956076066](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34956076066)
- **Accepted amendment:** [Contract](PUBLIC_ADMISSION_CONTRACT.md), [API delta](PUBLIC_ADMISSION_API.md)
- **Current implementation:** [Step A foundation](PUBLIC_ADMISSION_FOUNDATION.md), [1.1 byte specification](PUBLIC_ADMISSION_FORMAT_1_1.md)

## Current change

The contract amendment merged through [PR #151](https://github.com/patricklfdm/GeneralSearchEngine/pull/151)
at `72ea9a6b176a7371d708cea1d84ad8d603adef61`; [master CI 34960589647](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34960589647) passed.
The temporary CI/pressure-harness fix merged through [PR #152](https://github.com/patricklfdm/GeneralSearchEngine/pull/152)
at `716f06f6bb04dcbf86e775eb93b4f7f31799739a`; [master CI 34965248513](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/34965248513) passed with all Phase 1–5 gates executed.
Step A now adds the approved declarations, explicit v1-to-v2 inventory delta and
independent 1.1 bytes. The public builder and all newly declared operations remain
reserved. Local implementation evidence is recorded in its separate foundation report.

This is completion work between Phase 5 and Phase 6, not a renumbering of the charter.
The existing performance/cloud prerequisites remain in force.

## Ordered implementation PRs

Each PR starts after its predecessor has merged and its exact-master CI has passed.
The sequence is a concrete implementation plan, not permission to bypass these gates.

| Step | Deliverable | Public enablement at exit |
| --- | --- | --- |
| A — declarations and byte fixtures | Core configuration/transfer declarations, typed bootstrap/admin declarations, reviewed API delta, complete `1.1` storage/wire/receipt byte specification, independent positive/negative fixtures | Builder and mutating offline operations remain reserved |
| B — offline authority | Implement core configuration/transfer, typed source-preserving bootstrap, global decision/seals, resume, cleanup and non-voter replacement; independent crash inspection | Offline operations only; builder remains reserved |
| C — public runtime | Deferred build/start, complete role-aware application delegation, explicit activation/catch-up/reconstruction, local checkpoint, V4 backup, diagnostics and close | Enable only with the complete public-consumer gate in this PR |

Step A must resolve exact binary layouts/digest domains into checked-in independent
fixtures before B writes them. It retains legacy `1.0` parsing/fixtures and explicitly
rejects public `1.0` startup and `1.0`/`1.1` peer mixing. It may not silently change
Phase 1 inventory tests to ignore additions or substitute new golden bytes for old.

Step B uses preparation paths that cannot be mistaken for ready voters, even by
internal code. Step C refactors internal constructor/start and checkpoint behavior;
simply delegating the current constructor or quorum checkpoint does not satisfy the
contract. Core snapshot/planner settings must propagate into every private rebuild.
The `materialization` config supplies codec/schema/application bounds and portable
backup format; its directory is not opened as a competing V4 authority. V4-specific
WAL/derived-cache tuning creates no second writer or cache authority in the replica.

Every implementation PR records its exact changed files, test scope, generated
evidence, limitations, protected PR and subsequent master CI boundary. Once C is
accepted, Phase 6 begins with a separate entry plan and current cloud preflights.

## Required evidence matrix

Future tests below are requirements, not results claimed by this documentation PR.
Each failing case retains source/target hashes before reopen or cleanup.

| Boundary | Required positive and negative evidence |
| --- | --- |
| Configuration handoff | Manual/annotated/extended schemas, startup/dynamic indexes, nondefault snapshot/planner settings; mutation of original builder after capture has no effect; no thread/filesystem effect during capture/build |
| V4 source semantics | Pinned published V4.4 produces all three supported backup formats; read/import preserves sequence, canonical order, indexes and all query/ranking/page/highlight/explain results; changed bytes/codec/schema/indexes reject |
| Genesis identity | Empty and nonempty sequence-`S` groups; first application mutation yields `S+1`; controls do not; same IDs/different genesis cannot handshake; index-zero reopen reconstructs imported data; overflow rejects |
| Plan and resource admission | Repeat plan yields identical digest; caller-forged/stale plan, wrong member/leader/order/endpoint, alias/symlink, source overlap, occupied targets, low per-node/aggregate bounds reject before writes |
| Group publication | Real process kills after every target creation/force/verification, PREPARED, COMMITTING, receipt rename/force and each seal delivery; no pre-decision startable node; post-decision resume never deletes committed output |
| Resume and cleanup | Repeated resume, interruption, concurrent owner, source change before commit, missing source after commit, stale deletion plan, injected unknown member and damaged journal; cleanup only exact uncommitted inventory, source unchanged |
| Replacement | Follower disk replacement remains non-voting until verified catch-up; leader disk replacement fails with one survivor and succeeds with both; normal start never recreates absent authority |
| Lifecycle and role | Three separate JVM public consumers; build/start/activate/close races; activation retries/cancellation; every follower query/bulk/index/backup overload rejects before codec/queue work |
| Search and success | All single/bulk/index operations and inherited read overloads match published V4.4; leader success still follows entry quorum, proof quorum and atomic apply/publication; no-quorum reads expose only the last committed cut |
| Local maintenance | Follower and isolated readable leader checkpoint without remote ACK; unresolved suffix rejection; low capacity preserves old source; local checkpoint cannot advance floor/delete the sole recovery source |
| Backup round trip | Writer-ordered export during writes/checkpoint/close; V4.4 structural verification and restore of each export format; dynamic indexes/history/sequence intact; cancelled/lost response never deletes completed output |
| Observability and bounds | Consistent status/diagnostics in every state, unobserved/stale peers explicit, correct index-vs-sequence and metrics mapping; bounded/coalesced probes; no invented quorum evidence |
| Shutdown | Phase 5 interrupted/timeout/callback/concurrent close, partial record quiescence, queue accounting, startup and backup/transfer races; all accepted futures settle and ownership stays with a live writer |
| Regression and packaging | Phase 1–5 gates retained; published consumers/API compatibility; new API delta; nine JARs and two clean reproducible release builds; no workers/control codecs/fault fixtures in production JARs |

Independent Python parsers must understand the new manifest/genesis/receipts and
snapshot sequence offset without calling production decoding. They must reject
corrupted source bindings, mismatched receipt sets, altered genesis, seal-before-decision
traces, false base sequence and conflicting recovery evidence. Both Java and Python
must read the same frozen fixture bytes and agree on valid/invalid classifications.

The new public-consumer gate must compile outside the replication implementation
package against the production JARs. Its three JVMs use only the documented public
entry points for bootstrap/start/search/mutation/checkpoint/backup/replacement/close.
Test-only fault coordination may pause/kill owned JVMs but may not call package-private
initializers to create authority or private methods to stand in for public operations.
Raw results, exact process identities, source SHA/control JAR SHA, plans, receipts,
pre-reopen bytes and independent comparisons are retained on both success and failure.
The Required CI job must depend on this executed gate and always upload its evidence.

## Acceptance checklist

### Accepted documentation amendment (PR #151)

- [x] Phase 5 PR #150 and exact-master CI `34956076066` verified.
- [x] Required, Reactor tests, Compatibility, Release artifacts and no-GCP jobs passed.
- [x] Phase 1–5 master gates actually executed successfully.
- [x] Existing code gaps, exact proposed API delta and version amendment documented.
- [x] Publication/cleanup, lifecycle, backup, replacement and numeric bounds specified.
- [x] Ordered implementation PRs and independent public-consumer evidence specified.
- [x] Local documentation checks pass on the final diff: contract gate, 512 local links across 35 Markdown files, fence/whitespace checks and documentation-only scope.
- [x] Protected PR #151 accepts this amendment.
- [x] Exact-master CI `34960589647` accepts the merged documentation.

### Future public runtime acceptance

- [ ] Step A declarations, reviewed inventory delta and independent `1.1` bytes accepted.
- [ ] Step B source-preserving offline operations and crash/cleanup evidence accepted.
- [ ] Step C complete public runtime and real three-JVM public-consumer gate accepted.
- [ ] Public V4 backup/import round trip and published V4.4 semantic comparison pass.
- [ ] Full Phase 1–5 regression, compatibility, artifact and reproducibility checks pass.
- [ ] Protected master CI executes all required public-admission gates successfully.

## Historical validation for the documentation PR #151

The existing `scripts/verify-v50-phase0-contract.sh` passes. Local link validation
passes for 512 links across 35 Markdown files in the V5 map and root entry points;
code fences and new-document whitespace checks also pass. `git diff --check` passes.
The final scope is 16 Markdown files (13 updates and 3 new documents), with Java,
POMs, fixtures and workflows unchanged. Runtime tests are required in A–C when their
code changes; this documentation diff does not rerun process matrices or claim new
runtime evidence. Its protected acceptance receipts are recorded above; Step A validation is separate.
