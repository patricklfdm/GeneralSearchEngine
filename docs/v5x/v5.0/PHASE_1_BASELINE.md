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

The implementation-independent Python model exercises promise, append, durable ACK,
commit proof, apply, recovery floor and uncommitted suffix removal without importing
production Java. The deterministic transport serializes delivery, delay, duplicate,
drop and disconnect schedules into exact replay traces.

The local crash scaffold starts three concurrent JVM fixture workers in isolated
directories, records exact PIDs, kills only the configured-leader PID with `SIGKILL`,
restarts it as generation 2, drives a separately classified storage-fault exit on an
exact follower PID, restarts that worker, and validates a checksummed evidence bundle.
These workers are harness fixtures and never listen on a network endpoint or open
product storage. Bounded manifest/log/commit-proof/snapshot examples are generated and
validated by an independent Python inspector; they are compatibility fixtures, not a
writable replica-store implementation.

## No-paid cloud foundation

The manual `V5.0 Replication Foundation (No GCP)` workflow accepts only `plan` or
`fake`. It requests no OIDC token, invokes no `gcloud` command and creates no external
resource. The fake control plane represents three voters concurrently inside each
topology and serializes only independent topology repetitions. It records complete
VM, disk, firewall and staging-prefix cleanup receipts on success and injected
provisioning failure. A non-master dispatch fails closed before checkout.

The planning envelope is 8 vCPU plus 100-GiB data and 50-GiB boot disk per voter:
24 vCPU and 450 GiB provisioned disk at peak. Exact paid SKU, image, private firewall,
WIF identity and GCS prefix remain operator preflights for Phase 6; Phase 1 does not
claim their availability.

## Local reference toolchain

- OpenJDK `21.0.12+8` on Linux amd64;
- Maven Wrapper / Apache Maven `3.9.11`;
- Python `3.11.15`; and
- Linux `6.6.87.2-microsoft-standard-WSL2`.

CI independently uses pinned `actions/setup-java` and Python 3.11 declarations. This
local identity is diagnostic rather than a release-reproducibility claim.

## Local validation record

- full reactor: core 541 tests (4 skipped), replication 5 tests and processor 5 tests,
  with zero failures or errors;
- independent model/trace/format/fake-cloud suite: 11 tests with zero failures;
- separate-JVM `SIGKILL`, classified storage fault and restart evidence validation: pass;
- V1 through V5 independent consumer compilation: pass;
- release packaging: 9 JARs including main/sources/Javadocs for replication: pass;
- two-build nine-JAR reproducibility comparison: pass; and
- isolated-repository V1–V4.4 artifact checksum plus japicmp verification: pass.

## Phase 2 boundary

Phase 2 may implement only the replicated outer-format parser/writer, codec-free
inspection and follower durable append. It may not complete a client Future, publish
leader state from quorum, enable automatic leadership, or execute a paid cloud run.
