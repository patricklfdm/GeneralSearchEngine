# V5.0 Phase 1 foundation baseline

- **Status:** Local validation complete; protected-master acceptance pending
- **Coordinates:** `5.0.0-SNAPSHOT`
- **Starting master:** `105537c83921aaab8fc0d4cf911b043f1efac6e1`
- **Phase 0 acceptance:** protected PR #145, exact-master CI `34919817954`
- **Published control:** `general-search-engine:4.4.0`
- **Control SHA-256:** `0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`

## Delivered boundary

Phase 1 adds the optional `general-search-engine-replication` artifact as declarations
only. Its immutable values freeze the exact three-voter group, configured leader,
private endpoints, separate replica/materialization paths, finite resource bounds,
status, classified failures and offline bootstrap shape. Calling its engine builder,
storage inspector or bootstrap apply path fails explicitly: no production network,
replicated directory or quorum-success path exists.

The implementation-independent Python model exercises promise/incarnation fencing,
append, distinct durable-entry and proof ACKs, monotonic proof-gated apply, snapshot
recovery floor and uncommitted suffix removal without importing production Java.
Control entries leave application sequence unchanged; each document/index/bulk entry
advances it once. A durable proof protects history even when its ACK is lost.
The deterministic transport executes delivery, delay/reorder, duplicate, drop,
disconnect and reconnect schedules. Serialized payloads and traces drive the model;
seeded cases compare the resulting transcript and complete model state.

The [transport decision](TRANSPORT_AND_FRAMING.md) selects Java 21 NIO with no external
Maven dependency and freezes common binary framing. Sixteen golden message examples
have Python envelope validation and independent Java header/digest checks. The API
fixture now freezes full public/protected signatures, record component order, enum
values, nested types and constant values in addition to top-level type names.

The local crash scaffold starts three concurrent JVM fixture workers in isolated
directories, records exact PIDs, kills only the configured-leader PID with `SIGKILL`,
restarts it as generation 2, drives a separately classified storage-fault exit on an
exact follower PID, restarts that worker, and validates a checksummed evidence bundle.
Parent-observed PID, wait exit code and concurrent-lifetime records must agree with
retained raw worker logs/readiness/fault receipts. The final workers exit before
checksumming. CI uploads `target/v50-foundation` even after failure.
These workers are harness fixtures and never listen on a network endpoint or open
product storage. Bounded manifest/log/commit-proof/snapshot examples are generated and
validated by an independent Python inspector; they are compatibility fixtures, not a
writable replica-store implementation.

## No-paid cloud foundation

The manual `V5.0 Replication Foundation (No GCP)` workflow accepts only `plan` or
`fake`. It requests no OIDC token, invokes no `gcloud` command and creates no external
resource. The fake control plane models overlapping voter lifetimes inside each
topology and executes independent topology repetitions serially. Its event journal
tracks each VM, boot disk, data disk, firewall and staging prefix from creation
through deletion. An independent validator reconstructs resource/running sets,
checks three concurrent voters at measurement, and prevents the next topology before
cleanup. Partial provisioning and running failures retain evidence; incomplete
cleanup rejects the run. Recomputed checksums cannot hide inconsistent lifecycle
claims. A non-master dispatch fails closed before checkout.

The planning envelope is 8 vCPU plus 100-GiB data and 50-GiB boot disk per voter:
24 vCPU and 450 GiB provisioned disk at peak. Read-only catalog queries confirmed
`n2-standard-8` in `us-west4-a` and exact image
`ubuntu-2404-noble-amd64-v20260906`, ID `6257327608773510097`, READY without a
deprecated marker. The [availability receipt](cloud-availability.json) records
these observations and their limits. Fresh allocation capacity, quota headroom,
pricing, private firewall, WIF identity, GCS access and guest runtime remain Phase 6
preflights. No resource was created by this availability check.

## Local reference toolchain

- OpenJDK `21.0.12+8` on Linux amd64;
- Maven Wrapper / Apache Maven `3.9.11`;
- Python `3.11.15`; and
- Linux `6.6.87.2-microsoft-standard-WSL2`.

CI independently uses pinned `actions/setup-java` and Python 3.11 declarations. This
local identity is diagnostic rather than a release-reproducibility claim.

## Initial foundation validation record (`63ab9fa`)

- full reactor: core 541 tests (4 skipped), replication 5 tests and processor 5 tests,
  with zero failures or errors;
- independent model/trace/format/fake-cloud suite: 11 tests with zero failures;
- separate-JVM `SIGKILL`, classified storage fault and restart evidence validation: pass;
- V1 through V5 independent consumer compilation: pass;
- release packaging: 9 JARs including main/sources/Javadocs for replication: pass;
- two-build nine-JAR reproducibility comparison: pass; and
- isolated-repository V1–V4.4 artifact checksum plus japicmp verification: pass.

## Phase 1 refinement validation

The follow-up fixes the model counter/proof invariants, executes fault schedules,
replaces prewritten cleanup success with lifecycle simulation, strengthens evidence
admission, and closes transport/API/catalog decisions. Production Java and existing
artifact dependencies remain unchanged.

- reactor: core 541 tests (4 skipped), replication 8 tests, processor 5 tests;
- independent model/transport/format/wire/process-evidence/fake-cloud suite: 38 tests;
- real three-JVM SIGKILL/storage-fault/restart gate plus raw evidence admission: pass;
- independent V1–V5 consumer build/tests: pass;
- release packaging and nine-JAR artifact integrity: pass; and
- V5 documentation links and diff whitespace: pass.

These are local candidate checks. Protected Phase 1 PR acceptance and exact-master
CI remain pending. The initial two-build reproducibility and published-artifact
comparison above are historical checks; CI reruns them for the final PR source.
The model still abstracts storage and payload application. Full crash recovery,
V4.4 document/search-state equivalence and production force/publication barriers
belong to the later implementation matrix and are not claimed by this foundation.

## Phase 2 boundary

Phase 2 may implement only the replicated outer-format parser/writer, codec-free
inspection and follower durable append. It may not complete a client Future, publish
leader state from quorum, enable automatic leadership, or execute a paid cloud run.
