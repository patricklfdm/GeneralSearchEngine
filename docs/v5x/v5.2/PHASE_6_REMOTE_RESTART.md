# V5.2 Phase 6AJ SSH retained leader restart

This stage adds the second frozen M04 history, `leader-sigkill-retained-restart`,
to the [delivered receiver](PHASE_6_RECEIVER_DELIVERY.md) service. The original
four reads, four updates, carried token, successor progress, resource sampling,
retained restoration and physical/query oracles are unchanged. The previous
[partition/snapshot history](PHASE_6_REMOTE_PARTITION.md) remains available.

## One original crash and one explicit generation

Only the exact frozen restart profile admits generation 2. Every other service
still admits generation 1 only. The original generation receives a fixed crash
message with no caller-supplied PID, signal, path or shell. Its own service first
claims that crash, rejects pending public operations, and terminates its owned
JVM. A partial claim cannot be retried. The immutable original request/result
journal is retained; the crash never replays a business operation.

After observing SIGKILL exit `-9` and draining the original pipe reader, the guest
copies its authority directory to a separate pre-reopen directory. It rejects
links, special files and excess size/count before copying, forces the copy, checks
both original and copied inventories and publishes the original crash receipt.
The service exits normally and the lifecycle reports `CRASHED`. A failed,
uncertain, live or merely stopped service cannot authorize generation 2.

The second service uses a new configuration/session/socket on the same receiver
root. Before launch it verifies the original service/JVM have exited, their exact
identities and source match, the retained copy still matches its receipt, and the
live authority still equals that copy. After launch, repeated observations do not
require the now-advancing live authority to remain equal to the pre-reopen bytes.
An already consumed generation-2 launch only returns its original observation.

## Lost replies and evidence

The qualification deliberately discards the SIGKILL terminal stream reply. The
controller queries the original crashed service receipt and final journal event;
it never sends another kill. Its channel transcript retains the actual last
stream cursor and records the separate terminal query digest. It does not claim
the stream delivered a reply that was lost. The generation-2 launch reply is also
discarded; the existing lifecycle queries that same consumed launch without
starting another JVM.

Final stopped export includes both generations' configurations, identities,
journals and the guest's pre-reopen copy. The original generation has no separate
fabricated export. Its bytes are covered by the second generation's final export.
The controller downloads those bytes and supplies the unchanged M04 retained
validator with its pre-reopen directory. Independent checks bind the exact four
process generations, original crash receipt, snapshot inventories, original
request/response edges and controller crash-before-restart milestones. Guest,
controller and JVM times remain separate domains; no cross-host subtraction is
introduced.

## Local acceptance and boundaries

```bash
scripts/verify-v52-phase6-remote-restart.sh --skip-build
```

The gate compiles helpers from current sources, uses the existing unchanged Java
artifacts and creates a private loopback sshd. It retains a heartbeat every minute.
Its complete original history runs once; evidence mutations use disposable copies.
All installer/service/JVM/SSH owners must exit, including the crashed generation.

The complete gate passed in **104.727 seconds** at
`target/v52-remote-restart/run.kfNk6h/evidence/receipt.json`, binding base
`b1d2116aa00e033059a9011c3198a39243d28341` and executed checkout fingerprint
`ea5174f5714ac3b1fa58c87943643b44745feb11302368273d788f17d68f1908`.
Three receivers each received the same 42-file capsule and bootstrapped once.
Four original services/JVMs account for three first generations plus one retained
restart. Four reads and four updates passed; the crash and launch each submitted
once despite their dropped replies. Both physical/query/resource replays passed,
as did all **68 negative rejections**: 32 original M04, 22 restart and 14 delivery.

All 442 V5.2 Python tests (12 new restart tests) and 21 CI suite tests passed.
The tests cover exact profile/generation admission, changed/live predecessor,
partial crash claims, pending operations, failed retention, changed authority,
lost original sends and precise terminal query cursors. Lightweight tests join
the existing measurement CI step; the full SSH gate remains optional.

This is still single-host, loopback SSH qualification with a shared Python
checkout: `qualifiedMeasurement=false`, `fullRemoteQualification=false`,
`paidCloud=false`. General M01–M03 service admission, independent hosts/clocks,
complete owned cloud members, protected exact-source CI and fresh cloud admission
remain pending. No production Java, POM, frozen suite parameters or workflow
topology changes in this stage. No paid cloud or GitHub workflow was triggered.

Local logs, final file hashes and the complete commit path list are retained under
`target/v52-remote-restart/`. Acceptance documentation was added after execution;
the receipt keeps its actual executed source identity.

## Partition regression discovered during this stage

The additional unchanged partition history at
`target/v52-remote-partition/run.6a0GU7/evidence/receipt.json` failed to observe a
snapshot. Cut/heal ACK barriers took 0.908/2.459 seconds and the isolated target
became leader. That failed original is retained. Repeated Python/import/source
admission inside the fault window remained avoidable overhead even though the
three receivers' transitions were dispatched concurrently.

Partition control now reuses a bounded prepared SSH process per receiver. Full
source/artifact admission runs before its READY handshake, outside the fault
window. Every fixed request still checks configuration bytes, directory identity,
the existing voter lifecycle and the original forced transition claim/result.
An uncertain reply closes that stream and queries its original receipt over a
fresh authenticated stream; apply is not replayed. Four control channels and
eight messages per channel bound this optional controller. Private control owners
and every local stream are included in cleanup checks. Public calls, fault timing
parameters, runtime election settings and required snapshot evidence do not change.

This correction's full partition regression result is recorded separately from
the successful restart history above; neither receipt is relabeled or replaced.
It passed in **100.497 seconds** at
`target/v52-remote-partition/run.t99iMu/evidence/receipt.json`, with executed checkout
fingerprint `92bb0588b8a6537dfe5f3f2568464bb328eea1cdb0f1c3f960c2e8a52696684b`.
Its original cut/heal ACK barriers were **0.418/0.423 seconds**. All four reads,
four updates, required snapshot installation, 76 negative rejections and owner
cleanup checks passed. These finite observations demonstrate this run's result,
not an election/failover SLA or immunity to arbitrary scheduling delays.
The final Python suite has 448 passing tests, including six prepared-control
regressions, and the 21 CI suite tests pass.

After the shared SSH endpoint correction, the complete restart gate was executed
again on the final implementation. It passed in **102.110 seconds** at
`target/v52-remote-restart/run.Z3mhz8/evidence/receipt.json`, checkout fingerprint
`e16ce05678b760514f7e05b348323056e315b64fd9e5b05d3afd7387e2bdb08f`.
All eight original business calls, both portable replays, 68 negatives, single
crash/restart submissions and all cleanup checks passed again. This new execution
has its own source and receipt; it does not replace the earlier successful run.
Only this acceptance note and the handoff summary changed after final execution.
