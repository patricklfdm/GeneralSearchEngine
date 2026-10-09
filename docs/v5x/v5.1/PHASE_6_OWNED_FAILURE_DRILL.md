# V5.1 complete owned failure drill

**Status:** protected offline qualification accepted at PR #308, master
`bc805a4c922d77f1e7e5127694e20963a990e311`,
[CI 37837221623](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37837221623).
The complete twelve-cell lane and Required passed. This acceptance includes the
recipient-heartbeat correction below; previous failed evidence remains retained.
The twelve frozen fault cells now share one offline guest qualification scope,
source, verified build, package and modeled lease. Native admission remains limited
to the accepted four-cell experiment.

## Added guest scenarios

| Cell | Original fault and evidence | Cell ceiling |
| --- | --- | --- |
| interrupted-transfer | Nonselected recipient isolated from mutation/recovery traffic during the 4096-byte-value bulk, acknowledged live heartbeat, original exportable floor, first durable transfer chunk before ACK, SIGKILL and same-directory partial restart | 180 s |
| entry-chosen | Original 512-byte-value bulk stopped at ACCEPT_ACK_RECEIVED; chosen quorum and unresolved caller retained; surviving progress before old voter restart | 120 s |
| proof-quorum | Original bulk stopped at PROOF_ACK_RECEIVED; original forced proof quorum and unresolved caller retained; surviving progress before restart | 120 s |
| group-restart | All three original directories archived after graceful stop, restarted as new process generations, acknowledged state retained | 120 s |
| minority-capacity | PREPARE-only initialization barrier; node 3 sealed at 128 KiB and isolated from data with live heartbeats during two 20000-byte-value bulks, genuine capacity rejection/reply, bounded voter and healthy voter retained restarts | 180 s |

The existing leader-loss, maintenance, no-quorum and four
[network/lag cells](PHASE_6_OWNED_NETWORK_FAULTS.md) complete the twelve-cell set.
Document encoding limits stay exactly 4100/20004 bytes in the two frozen large
payload cases. Other voters retain the sealed 64 MiB limit. Public call caps,
progress/rejoin limits, original network holds and cut hooks are unchanged.

### Recovery recipient election regressions

Master CI [37761664548](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/37761664548)
failed `interrupted-transfer` with `owned original durable cut missing`. The
original full partition also dropped heartbeats. During the 4.9-second isolation,
node 3 began a campaign, then became the epoch-10 leader after healing. It recovered
through its selected basis instead of receiving a snapshot. Its cut remained
armed, with no incoming snapshot chunk after healing. The 60-second progress
deadline expired; the 180-second cell and 1800-second outer command did not expire.

The complete local regression then exposed the same mechanism in
`minority-capacity`: node 3 campaigned during its 4.4-second full isolation and
rejected a 146632-byte campaign reconstruction against its 131072-byte limit.
There was no original CAPACITY_EXCEEDED wire reply from a receiving follower, so
that required evidence never arrived. The unchanged capacity case failed; it was
not counted as passing because the transfer case succeeded.

Both owned recovery setups now block only the closed mutation/recovery request
types on target edges, including PREPARE and basis/selected exchange, while
allowing normal heartbeats and status probes. The controller waits for an original successful
heartbeat reply from the lagging target acknowledging the active source's new
proven index before healing (and before arming the transfer cut). No election policy
or engine state is changed. The recipient is healed before any source can deliver
the held data, preserving original guest-clock ordering.
A new target campaign fails immediately with the observed campaign retained.
Independent replay requires the actual heartbeat during isolation, the still
lagging reply, and no target campaign through the durable cut or original resource
rejection. Missing heartbeat
and unexpected campaign mutations must be rejected along with the existing
original chunk, cut, SIGKILL, capacity reply and unchanged partial-directory checks.

This is a correction to fault setup, not a retry or a larger timing budget.
Original failed evidence remains retained. Corrected-source protected CI is
required before accepting the complete owned failure drill.

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
