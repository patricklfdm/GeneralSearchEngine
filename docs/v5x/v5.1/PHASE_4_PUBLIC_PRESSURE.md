# V5.1 Phase 4K: public transport pressure and slow force

**Status:** local qualification passed. Protected Batch K and complete Phase 4
acceptance remain open. [Batch J](PHASE_4_PUBLIC_CANDIDATES.md) is accepted through
PR #201 at master `04106a0c2e88010c2c14c43ad485bc3113ed1d05`, exact-master CI
`35698045261`; all eleven full-CI lanes and the Required gate succeeded.

## Public execution and boundaries

`scripts/verify-v51-phase4-public-pressure.sh --skip-build` compiles external public
consumers against packaged candidate JARs. All bootstrap, startup, atomic bulks,
strong reads and close operations use public APIs. The controller may pause real
transport/storage boundaries, close owned sockets and restart an owned JVM. It
cannot manufacture votes, activate leaders or repair retained authority.

The package-private transport observer gains a no-op-by-default accounting method.
It reports admission, capacity rejection and release for actual reservations;
identity tokens distinguish two attempts carrying identical request bytes. The
test observer gives each token a process-local serial and retains exact encoded
outbound frames. Release is observed immediately before the production counters
are released, with counter release in `finally`, including observer failure.
Production behavior retains two outbound reservations per peer, four in total,
eight inbound connections and a four-frame byte budget. Public API, limits and
wire/storage formats do not change. This is an internal production observation
seam change, so the replication candidate JAR hash changes.

Every group seals the existing fixture election policy: 3.6–6 seconds on nodes
1/2 and 600–601.2 seconds on node 3. Request timeout is 1200 ms. The leader slow-force
case seals one pending public operation; other cases retain sixteen. The oracle
reads these values from the PLAN inside the actual bootstrap SEAL. These are public
test configurations, not new product defaults or performance guarantees.

## Five scenarios

| Case | Schedule and required outcome |
| --- | --- |
| `outbound-saturation` | Hold two real requests to the non-quorum peer before request write; observe a later capacity rejection while both reservations remain held. The healthy quorum acknowledges a new bulk and strong read before release. |
| `inbound-saturation` | Send independently encoded valid HANDSHAKE frames and hold eight responses at the non-quorum peer. A further valid probe must end in EOF/reset, and the observer must report rejection while all eight connections remain held. The healthy quorum continues serving. A timeout is not rejection evidence. |
| `slow-follower-accept` | Pause the selected quorum peer after exact ACCEPT bytes are written but before force, for longer than the request timeout. Preserve the original public mutation's `INDETERMINATE` outcome. Release, observe its exact force, then resolve the uncertain atomic bulk by public strong read. |
| `slow-follower-proof` | Apply the same schedule at PROOF write-before-force. No successful ACK for that exact record may escape during the pause. Preserve the uncertain result and resolve it after release. |
| `slow-leader-accept` | Pause the leader's ACCEPT before force. With one admitted pending client, reject a second write as `NOT_SUBMITTED` and a read as `NOT_APPLICABLE`, both with `CAPACITY_EXCEEDED`. Release and conservatively handle the original result, then prove fresh public service. |

For saturation, temporary PREPARE request loss excludes node 3 from the initial
write quorum; the rule is removed after natural public activation. The actual
forced seed PROOF must identify nodes 1/2 as its voters. Slow-follower cases instead
select the actual quorum peer from that proof. This matters because automatic
writes use the selected quorum peer; its timeout may end the original operation
before another campaign restores service. The suite does not assume automatic
per-operation replacement of a slow quorum peer.

Each slow-force pause lasts at least 1.4 seconds after controller observation;
process-local timestamps independently prove it spans the request deadline.
Complete pre-force bytes are not labelled durable, and a pause is not a power-loss
test. An uncertain mutation is never replayed. A fresh read must contain either the
whole unique bulk or none of it; a successful mutation must be present. The full
client history and independently decoded chosen prefix validate that observation.

After release every case acknowledges another unique bulk, reads it, waits for the
pressured voter to catch up and closes/reopens the current leader using its retained
directory. The pre-reopen authority archive and final public read are retained.
All admitted transport reservations must be accounted for through final public close.

## Independent evidence

The [pressure oracle](../../../scripts/v51/public_pressure_evidence.py) combines
independent client-history and decoded quorum/read checks with:

- Reservation lifetimes bound to PID and unique token, exact outbound frame bytes,
  per-peer/global/inbound peaks, and no missing, duplicate or changed releases.
- Actual saturated rejection between the last hold and first release, linked to
  real admitted frames or controller-retained HANDSHAKE probes.
- Same-process pre-force bytes, pause/release order, deadline-spanning duration,
  exact later force and absence of an early success ACK.
- Public rejection classifications, no forced occurrence of the rejected bulk,
  no write replay, and later successful reads/writes after pressure release.
- Negative variants removing accounting, holds, releases, force observations,
  resumed success or resolution reads; shortening pauses; or relabelling uncertain
  work as safely retryable. Unit witnesses separately cover reservation identity,
  byte/slot limits and false force ordering.

Three Java transport regressions cover cancellation while a sender still owns its
reservation, observer/encoding failures, and close interrupting held senders.
The shared observer's normal path remains active in existing public gates.

CI adds this gate to `v51-public-lifecycle` with an always-retained
`v51-public-pressure-${{ github.sha }}` artifact for fourteen days. Existing gates,
eleven required lanes, docs-only routing and paid-cloud behavior remain unchanged.

## Remaining work

This supplements E10/E11. It does not qualify every internal runtime mailbox,
thread/OS resource failure, snapshot-staging limit, epoch/promise-count/ancestry
exhaustion, or ambiguous/conflicting frozen selection. The remaining E01–E12
mapping and protected Phase 4 acceptance still require explicit qualification.
Published V5.0 authority, versions, dependencies and cloud experiments are unchanged.

## Local validation

Base: `04106a0c2e88010c2c14c43ad485bc3113ed1d05` plus this batch.
- Complete five-case gate passed in
  `target/v51-public-pressure/run.byPNEV/evidence/receipt.json`: 52 public application
  calls, 20 runtime process identities and 65 rejected evidence-negative variants.
- Final independent review of all five retained cases passed with the stricter
  force-to-public-bulk binding. `target/v51-public-pressure/final-oracle-review.json`
  binds the matrix receipt and final oracle hashes. Final inbound reset handling
  also passed in `target/v51-public-pressure/final-inbound/receipt.json`.
- Targeted reactor package passed 19 Java tests, including the three new transport
  regressions, `V51AutomaticRuntimeTest` and `V51PublicRuntimeTest`:
  `target/v51-public-pressure/build.log`. This is not a full local reactor test run.
- Existing public runtime gate passed with four JVM identities and retained failover:
  `target/v51-public-runtime/run.7WUAoX/evidence/receipt.json`. The shared observer's
  existing `before-reply-kill` promise case passed under
  `target/v51-public-pressure/shared-peer-promise/receipt.json`.
- All 162 V5.1 Python tests and 25 CI/toolchain tests passed. YAML, 101 shell blocks,
  30 unique artifact names, unchanged existing CI steps/required jobs, the original
  87-row migration map, 33-document contract, local links and whitespace passed.
  The V5.0 contract and protected historical files remain unchanged.

Candidate JAR SHA-256:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `b5c6ae4aa10238295eea80e9a523c28c2c127defd7290a174b1e17968d7b0680`.

Exploratory failed schedules remain retained under `target/v51-public-pressure`.
They exposed fixture assumptions about the selected quorum, rejection timing and
an aliased read-result list; those fixtures were corrected without changing the
protocol's quorum selection or uncertainty semantics. Execution-time inventories
precede final documentation and independent-oracle review. Each protected CI lane
still builds/tests its own reactor; hosted-runner qualification remains pending.
