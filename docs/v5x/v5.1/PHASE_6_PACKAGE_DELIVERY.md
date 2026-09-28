# V5.1 Phase 6C3C7 — complete package delivery and persistent services

**Status:** accepted through PR #238, master
`ef7562bc60a0a15ab4202367c5e286fe6250cbdb`, exact-master CI `36302498537`
attempt 2 (all 27 jobs). Attempt 1 failed the inherited automatic-healthy rich
workload gate and skipped its aggregate; that failure remains retained. The
successful rerun does not establish its root cause. Full 6C and paid admission
remain open. The [owned-startup candidate](PHASE_6_OWNED_SERVICES.md) follows this slice.

## Delivery contract

[The controller](../../../scripts/v51/guest_package_delivery.py) transfers the
existing complete JRE, five-JAR, adapter, Python and frozen-plan archive to a
distinct private installation for each attempt/node. It preserves the transport's
1 MiB request maximum: the archive is divided into at most 256 ordered parts,
each with an exact byte count and SHA-256. The descriptor binds source, complete
archive digest, workload, build manifest, package manifest, numeric instance/data
disk IDs and the access-descriptor digest. Native cloud delivery remains closed.

[The receiver](../../../scripts/v51/guest_package_receiver.py) travels as trusted
controller source over the pinned SSH command. It imports no staged package code
during delivery. It forces exclusive request, part and installation claims before
consuming input or unpacking. Part digests, the complete archive digest, the closed
regular-file inventory and the existing package source/build/classpath checks all
precede a forced success receipt. Failed or incomplete claims remain consumed.

All transfer connections share one original boot-bound guest deadline (maximum
600 seconds). A lost response permits receipt queries only; it never resubmits
the uncertain part or installation. New deadlines cannot renew retained claims.
The controller caps its connection log at 4096 entries and retains at most eight
bounded failure diagnostics. Parts and the assembled archive remain available for
diagnosis. The sender does not retry measurements or mutate frozen workload limits.

Every delivered service connection first verifies the successful installation,
unchanged package, exact configuration binding and current boot. A completed
installation may serve after its transfer deadline; that deadline does not replace
the existing service lifetime or command deadlines. Start, submit, query, cancel,
shutdown, readiness and binary collection use the existing service protocol.
No package Python is imported before these checks.

## Qualification boundary

[The integration gate](../../../scripts/v51/guest_package_qualification.py) uses
an actual ephemeral loopback OpenSSH server and seven distinct package installations:
one published V4.4 local node, three published V5.0 configured nodes and three
candidate V5.1 automatic nodes. Each delivery deliberately loses its first completed
part reply and its final installation reply, requiring exactly two queries and one
execution of each write. Private keys remain outside the evidence tree and are
removed when the server closes.

The existing independent mount-view bootstrap remains a separate gate. The SSH
gate uses distinct package installations on a shared local filesystem, retaining
the existing per-mode source preparation. All service control and collection
connections use real SSH.
Each mode executes the existing ten-call warmup, observes a lost command response
without replay, rejects collection while the JVM is active, collects complete
journals after clean stop, and shuts down/reaps the persistent services. The
automatic mode retains its interrupted-download rejection. No scenario is removed.

Provider IDs and account metadata are explicit fixtures. The shared local
filesystem is not IAP or an actual cloud data disk. The separate bootstrap gate's
optional hosted sudo fallback only creates private mount views. This
gate reports `realSshExecuted=true`, `engineWorkloadExecuted=true`,
`realBlockDeviceWritten=false`, `paidCloud=false`, `fullRemoteQualification=false`.
It does not establish full cloud workload/physical-oracle acceptance.

The foundation job adds this gate with a 900-second outer limit and a separate
`v51-guest-delivery` artifact (seven-day retention, compression level 1). The earlier
plain packaged-service and isolated-bootstrap gates remain. Receiver regressions run in foundation and
the no-GCP provider lane; synthetic package fixtures make no engine claims.

```bash
python3.11 -m unittest scripts.v51.test_guest_package_delivery
# Requires an exact-source cloud_bundle output and pinned build toolchain:
python3.11 -m scripts.v51.guest_package_qualification target/package-services \
  --bundle target/v51-guest-package --source "$(git rev-parse HEAD)"
```

Remaining work connects owned cloud startup, actual mounted-volume service
admission, distributed faults/oracles and evidence budgets, then trusted preflight
and separate V5.1 workflows. User confirmation and manual paid triggering remain
required at their existing boundaries.
