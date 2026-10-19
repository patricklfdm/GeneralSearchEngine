# V5.2 Phase 6AD SSH command transport and guest identity

This stage connects [stable whole-history commands](PHASE_6_REMOTE_OWNED_HISTORY.md)
and the [receiver-local backend](PHASE_6_REMOTE_HISTORIES.md) through real pinned
OpenSSH channels. It is a local transport qualification, not three-host placement,
provider ownership, full member aggregation or paid admission.

## Original execution survives connection loss

`remote_ssh_guest.py` is a fixed control entry: probe, prepare, submit, query,
cancel and inspect. The only executable command is the existing closed
`execute-history` slot. Requests cannot carry shell text, arbitrary argv or
individual measured reads/updates. The original detached owner still holds the
three local JVM pipes and executes the unchanged whole-history controller.

A forced immutable launch claim precedes process creation. A duplicate or a
partial launch publication cannot create another executor. If the process launch
fails after its claim, subsequent observations report uncertainty and fail after
the existing bounded uncertainty threshold. They never retry history execution.
The worker separately forces its boot/PID/start-ticks identity before handler
entry and retains its exit observation. Preparation is idempotent only for the
same complete configuration; it never clears consumed command state.

The controller reuses a private foreground SSH master. Each channel is sent once;
a broken master cannot silently fall back to another connection. The next query
can establish a new pinned connection to observe the original durable command.
Disconnecting the controller closes SSH resources, not the detached experiment.
Cancellation remains cooperative and retains original outcomes. Operational
observation budgets warn; exchanges have finite deadlines and the existing
transient/permanent-error and uncertainty thresholds remain in force.

## Identity and error boundaries

Strict host-key checking, one pinned Ed25519 key, isolated known-hosts files,
public-key-only authentication and disabled agent forwarding are explicit. Key,
pin and target changes reject before another connection. Generated private keys
and master sockets live in temporary private directories outside retained
evidence and are removed on exit.

A probe over that authenticated channel captures the actual Linux boot ID,
user ID, and the private parent directory's device/inode identity. Every
control request checks those values, the original source/checkout fingerprint,
the complete suite/history/session binding and the exact configuration digest.
Responses repeat the observed host identity and configuration digest. Process
start/end clocks are validated only within that guest's clock domain; no
controller/guest timestamp subtraction is introduced.

Host/source mismatch and invalid requests return closed error codes without raw
exception text or credentials. Authentication and host-key failures are permanent;
only recognized connection interruption follows the existing bounded query path.
This reuses the established V5.1 bounded subprocess and SSH master mechanics;
V5.1 execution, schemas and admission are unchanged.

The new endpoint deliberately accepts only loopback SSH. Directory device/inode
identity is a local resource observation, **not a GCP instance or disk identity**.
Configuration and selection are explicitly synthetic/non-admitting. A real
cross-host backend still needs independently admitted instance/disk facts,
verified delivered helper bytes, per-voter persistent execution and correct
cross-host evidence ordering. Private IP addresses alone cannot enable it.

## Local qualification

After packaging the current unchanged runtime JARs, on Linux with `ssh`, `sshd`
and the existing local sshd prerequisites available:

```bash
scripts/verify-v52-phase6-ssh-history.sh --skip-build
```

The entry starts a private loopback sshd with temporary keys and configuration;
it does not change the machine's sshd configuration, `~/.ssh`, accounts or disks,
and uses no sudo or GCP API. It tests wrong host/source identity, wrong host key
and authentication, then executes one real untimed candidate-minimum history.
The submit response is deliberately discarded and its connection closed. Queries
on a fresh connection must observe the same original execution; another duplicate
connection must return its identical terminal receipt. Alternate command IDs
reject, repeated prepare cannot erase the result, and the original executor and
all three JVMs must stop. Original/relocated physical and query validation remains
mandatory. Long observation emits a heartbeat approximately every minute.

Only lightweight unit regressions are added to the existing measurement CI entry.
The real SSH probe is an optional operator gate; it is not added to every PR.
Receipts remain `qualifiedMeasurement=false`, `fullRemoteQualification=false`,
`syntheticSelection=true` and `paidCloud=false`. The complete 28-history cohort is
not rerun or reclassified by this transport check.

Actual local results and the executed working-tree fingerprint are retained under
`target/v52-ssh-history/`; full protected CI and fresh cloud admission remain open.

## Retained local result

`target/v52-ssh-history/run.5T2XBP/evidence/receipt.json` passed all nine control
cases and one real untimed receiver history: 11 reads, three updates and 24 exact
negative rejections at each of the original and relocated locations. The original
was submitted once, observed with 41 queries and verified over three successive
pinned control connections. The executor and all three JVMs stopped normally;
no forced executor cleanup was needed. History execution, replay and final
duplicate/exit checks took 55.353 seconds locally, not a cloud performance result.

The executed base is `6347364565ffdffc1e0eaba2f1984f5e5fd8a20b`, with working-tree
fingerprint `a6aa7eafc4a185706405a68e9a14151038c176fbc25e2818be5168811338e068`.
This record was added after execution. Existing unchanged Java artifacts were
reused and history helpers compiled freshly; no new reactor build, 28-history
cohort, GitHub dispatch or paid experiment ran for this stage.

The first attempt `run.zXC6AM` failed before guest preparation because this local
OpenSSH rejects a world-writable `/tmp` ancestor of `AuthorizedKeysFile`. Its
failure and daemon log remain retained. Temporary server keys now use a private
directory under ignored `target`, outside the retained evidence; strict modes
remain enabled and the temporary directory is removed after the run. The failure
was fixed in qualification setup, not retried as a business workload.

All 322 V5.2 Python tests, including 17 new SSH/identity/launch regressions, and
21 CI suite tests passed. Summary and raw-receipt hashes are retained in
`target/v52-ssh-history/validation-summary.json`.
