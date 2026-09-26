# V5.1 Phase 6C3C1: persistent guest and transport integration

**Status:** 6C3C1 accepted through PR #232, master
`2183dafa618238f0b824fc0a3b3d42624ce24782`,
[exact-master CI 36124423253](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36124423253)
(all 27 jobs passed, including the persistent guest gate).
[6C3C2 bootstrap/startup preparation](PHASE_6_GUEST_BOOTSTRAP.md),
[6C3C3 owned startup](PHASE_6_GUEST_STARTUP.md) and
[6C3C4 helper delivery](PHASE_6_GUEST_DELIVERY.md) were subsequently accepted through
PRs #233–#235. The [6C3C5 deadline candidate](PHASE_6_GUEST_DEADLINES.md) follows them.
Full 6C3C, trusted cloud configuration and paid admission remain open.

The first PR #232 rich automatic-healthy attempt, run `36120650925`, failed after
an INDEX_CREATE succeeded in 1290 ms and the next frozen arrival found its lane
busy. The rerun and exact-master pass do not identify the host/I/O timing cause.
No measured call retry or deadline relaxation was introduced. The original failure
is retained locally under `target/ci-review-36120650925/`.

## Implemented integration

The immutable package now includes a closed Python dependency set and both frozen
plans. Its standalone verifier validates those bytes before loading the guest
entry point. A per-voter service owns a persistent JVM and its pipes; controller
connections carry lifecycle commands or whole frozen windows. Individual timed
GSE calls stay on the issuing guest and use the existing four-lane JVM protocol.
No measurement is issued over one SSH connection per API call.

[cloud_guest.py](../../../scripts/v51/cloud_guest.py) uses the accepted durable
[command store](../../../scripts/v51/remote_command.py). The claim and request are
forced before handler entry. The detached service outlives its launch/submit CLI;
a lost submit response permits only queries of that original identity. Duplicate
IDs return their existing receipt, and a busy guest rejects before another claim.
A stopped/uncertain daemon cannot silently start a second executor from the same
launch claim. Query and cancellation remain available independently of its executor.

The service's Unix socket has an owned private directory, mode 0600, bounded
messages and peer-UID checks. The short socket path is derived from the full guest
root identity to work with long CI evidence paths. Guest identities bind source,
complete package digest, attempt, node and frozen workload; configuration also
binds the package manifest, mode, absolute cell root, group and three endpoints.
A changed binding, host, group, package or root is rejected.

[guest_jvm.py](../../../scripts/v51/guest_jvm.py) retains actual PID, Linux process
start ticks, boot identity, argv, ready response, original operation IDs, exchanges
and shutdown outcomes. A dedicated reader dispatches replies to their original
pending calls. It never reissues a timed call after a missing response. Normal
shutdown closes and reaps the owned JVM and reader; failure shutdown kills that
owned subprocess and retains the incomplete outcomes. A service has one bounded
5400-second lifetime. This local lifetime does not restart a controller lease or
replace per-cell timing accounting.

## Endpoint and lifecycle boundary

The two existing Java measured adapters now accept an explicit three-line
`hosts.txt` alongside `ports.txt`; numeric private IPv4 addresses are supported.
Loopback addresses support local qualification. The existing ports-only path still
uses its original loopback defaults. The helper is compiled independently against
each mode's JARs. No production API, voting, proof, resource bound or timing policy
changes.

Closed service commands prepare a V4.4 source and per-mode bootstrap, start the
assigned voter, inspect status, activate only the configured V5.0 leader, execute
an existing frozen window, stop the voter and collect its stopped evidence. They
do not accept arbitrary executables, Java main classes or shell programs.
The three hosts must use their configured absolute cell paths. Bootstrap seals
also bind parent filesystem identity, so [6C3C2](PHASE_6_GUEST_BOOTSTRAP.md) imports
one source backup and seals initial authority locally on each receiving host. This batch's qualification uses distinct TCP loopback hosts
and per-voter stores on one filesystem; it does not prove bootstrap transfer across
independent VM filesystems. Source distribution, data-mount verification and the
remaining fault orchestration are the next integration boundary.

## Transport and collection

[guest_transport.py](../../../scripts/v51/guest_transport.py) runs bounded process
connections with nonblocking stdin/stdout/stderr, an original deadline, response
and diagnostic byte limits, and process-group cleanup. The local backend actually
executes the packaged CLI in a separate process for every control connection.
A retained guest command can therefore finish after that connection has exited.

The SSH builder selects only the attempt's key, disables ambient SSH configuration
and multiplexing, requires an exact-instance host-key alias and a supplied pinned
Ed25519 host key, and quotes remote argv. The IAP proxy uses
[`gcloud compute start-iap-tunnel --listen-on-stdin`](https://docs.cloud.google.com/sdk/gcloud/reference/compute/start-iap-tunnel).
Host-key and identity choices follow the
[OpenSSH configuration reference](https://man.openbsd.org/ssh_config.5).
The live SSH backend remains disabled until host keys, per-attempt guest access,
provider identity and paid admission have trusted producers. Its command construction
is tested offline; no actual IAP tunnel or SSH server handshake is claimed.

Collection requires a stopped JVM. Each service exports only its own closed
command receipts, windows and JVM observations. The existing binary packer hashes
and bounds the files; each downloaded part is independently size/hash checked before
extraction. An interrupted immutable part may be fetched into a fresh directory;
its failed `.partial` remains retained. That permission never authorizes another
workload submission. Full authority capture, combined multi-guest evidence budgets
and the physical/history oracles remain necessary for complete remote qualification.

## Qualification

```bash
python3 -m unittest scripts.v51.test_guest_service
python3 -m scripts.v51.guest_qualification target/v51-guest-service \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)"
```

The second command requires the exact-source package and successful verified-build
receipt from 6C3B. CI reuses that package in `V5.1 foundation and runtime`, with a
900-second subprocess backstop and always-retained evidence. No new Required job
or Maven build is added; original gates, dependencies and docs-only decisions remain.

Three real-JVM cases exercise published V4.4 local, published V5.0 configured and
candidate V5.1 automatic mode. Each executes the frozen experiment healthy warmup
(10 calls) on the guest, discards the initial submit reply and recovers solely by
receipt queries. The scheduler independently checks that window. Actual JVM
exchanges must contain exactly those calls with successful outcomes; querying and
resubmitting the consumed command ID after shutdown must return the same receipt.
This diagnostic subset is not an experiment or canonical member.

The cases also reject collection while a JVM is active, perform graceful close,
download/replay all guests' binary evidence, reject a truncated part, and verify
service/JVM termination. Linux subreaper handling lets the local qualification
reap the detached guest processes it launched. Focused regressions cover duplicate
requests, busy admission, cancellation, claim-before-handler, private endpoint
configuration, original deadlines, subprocess output bounds, SSH quoting, key
permissions, wrong host identity and the disabled live backend.

Receipts state `execution=local-guest-service-only`, `engineWorkloadExecuted=true`,
`paidCloud=false`, `fullRemoteQualification=false`. They qualify this transport and
lifecycle slice, not three actual VMs, an SSH host-key bootstrap, every failure cell,
a public failover SLA or the complete physical/history semantics. Local results
are retained at `target/v51-guest-review/`; the exact-master run above accepts this slice.

## Next batch

Continue with [6C3C2 bootstrap and startup preparation](PHASE_6_GUEST_BOOTSTRAP.md),
then complete actual guest data-mount execution, remote fault wiring and independent
complete evidence validation. Then integrate trusted image/IAM/quota/retention/GitHub/pricing
observations, V5.1 WIF/environment configuration and separate runner/manual/scheduled
cleanup workflows. Real provider mutations remain disabled. Paid experiments remain
manually triggered by the user after exact-request confirmation.
