# V5.1 complete owned failure drill

**Status:** implementation candidate; corrected-source protected CI is pending.
The twelve frozen fault cells now share one offline guest qualification scope,
source, verified build, package and modeled lease. Native admission remains limited
to the accepted four-cell experiment.

## Added guest scenarios

| Cell | Original fault and evidence | Cell ceiling |
| --- | --- | --- |
| interrupted-transfer | Nonselected recipient isolated during the 4096-byte-value bulk, original exportable floor, first durable transfer chunk before ACK, SIGKILL and same-directory partial restart | 180 s |
| entry-chosen | Original 512-byte-value bulk stopped at ACCEPT_ACK_RECEIVED; chosen quorum and unresolved caller retained; surviving progress before old voter restart | 120 s |
| proof-quorum | Original bulk stopped at PROOF_ACK_RECEIVED; original forced proof quorum and unresolved caller retained; surviving progress before restart | 120 s |
| group-restart | All three original directories archived after graceful stop, restarted as new process generations, acknowledged state retained | 120 s |
| minority-capacity | PREPARE-only initialization barrier; node 3 sealed at 128 KiB, two 20000-byte-value bulks, genuine capacity rejection/reply, bounded voter and healthy voter retained restarts | 180 s |

The existing leader-loss, maintenance, no-quorum and four
[network/lag cells](PHASE_6_OWNED_NETWORK_FAULTS.md) complete the twelve-cell set.
Document encoding limits stay exactly 4100/20004 bytes in the two frozen large
payload cases. Other voters retain the sealed 64 MiB limit. Public call caps,
progress/rejoin limits, original network holds and cut hooks are unchanged.

## Command and evidence boundaries

Closed guest actions derive the cut, payload sizes and network rules from the
configured case. Claims precede fault injection and target submission. An
uncertain submission can only query its original receipt; it cannot replay a
mutation. SIGKILL requires the current JVM's original CUT_REACHED event. Unresolved
crash calls retain PENDING with disconnect observation and no invented response.
Graceful retained restarts preserve the same authority directory and immutable
identity bytes, with inventories captured before the new JVM starts.

The independent validator binds original guest commands, controller observations,
public histories, sealed configuration and process generations. It checks actual
wire quorums, proof forces, transfer chunks, capacity accounting and all retained
restart archives. Negative variants remove original cuts/quorums/chunks, fabricate
responses, change capacity accounting, omit initialization barriers or omit retained
restarts. A partial, reordered or mixed-source set cannot pass the aggregate.

## Offline entry and CI

```bash
python3.11 -m scripts.v51.guest_owned_qualification \
  target/v51-owned-failure-drill --bundle target/v51-drill-package \
  --source "$(git rev-parse HEAD)" --failure-drill --allow-sudo-namespace
```

Create the package first with `scripts.v51.cloud_bundle` and a fresh exact-checkout
`scripts.ci_v51_bundle` manifest. The qualifier deliberately loses original submit
replies and observes durable receipts without resubmission. It collects all twelve
original groups under one bound request, then independently replays their evidence.
The dedicated required CI job restores the verified build and uses isolated mount
views; original failures and consumed claims are always retained. On hosts without
mount namespaces, `--fault-local` records separate local directories and makes no
independent mount-view claim. Both paths use real SSH and JVMs with modeled provider
resources, and neither accesses GCP.

Full remote qualification stays false. This scope does not admit or price a paid
failure-drill request. Next are canonical rich schedules/control placement, the
complete fifteen-cell aggregate, and explicit native preset budget/admission review,
as described in the [full-preset entry plan](PHASE_6_NATIVE_PRESET_ENTRY_PLAN.md).
