# V5.2 Phase 6AI SSH partition and snapshot recovery

This stage extends [receiver delivery](PHASE_6_RECEIVER_DELIVERY.md) to the complete
frozen M04 `follower-snapshot-carried-token` history. Its original selected-pair
observation, four updates, four reads, baseline/source floors, snapshot installation,
carried tokens, resource samples and physical/query oracles remain unchanged.
It uses the existing JVM observer's closed bidirectional single-voter cut. This
qualifies that observer fault over SSH; it does not qualify provider firewalls.

## Exact history admission

The service and delivered capsule admit only the previous untimed histories plus
this exact M04 profile. The capsule additionally binds and transfers the frozen
`measurement-fault.json`. Different fault cases, edited timing/operation parameters,
mixed smoke flags, additional files and altered delivered inputs reject before a
voter starts. General measured M01–M03 and SIGKILL/restart service generations are
not enabled by this change. The frozen suite JSON and its hash are unchanged.

## Original transitions and barriers

Each receiver gets a fixed `apply`/`query` endpoint. It binds the existing service
configuration, boot/user/directory identity, source and declared target. It can
install exactly one original cut, followed by one original heal, in the selected
receiver's fixed observer control file. It accepts no shell, arbitrary path,
process ID, firewall rule or caller-provided bytes. A nonblocking per-receiver
lock rejects overlapping transitions.

A forced request claim precedes the file update. The new bytes are forced and
atomically renamed before the result receipt is published. A repeated exact
request returns its original receipt without writing again. Partial claims or a
lost executor stay uncertain; observing a matching control file alone cannot turn
them into successful operations. Changed targets reject; observing an old cut
after heal never reapplies it, and the controller rejects its obsolete live state.

Before workload activation the controller establishes each pinned control channel
with a read-only freshness query. It sends each transition once, concurrently to
the three original receivers, and waits for every original response before any
cleanup. This avoids introducing a serial SSH setup delay into the frozen fault.
A lost transport response queries only that transition; source, host-key,
authentication and malformed-request errors fail immediately. A missing or partial
query result fails without consuming the whole phase budget. Each SSH exchange
keeps its finite existing deadline; there is no new whole-history time ceiling.

Only after all three original acknowledgements arrive does the unchanged M04
controller continue. Separate guest clocks establish each receiver's local
cut-before-heal order; controller clock records establish all-ACK-before-business
and all-ACK-before-snapshot-observation barriers. No cross-host clock subtraction
or timing SLA is inferred.

## Cleanup and independent evidence

If the history fails partway through control, cleanup attempts a separate heal on
every launched receiver, continuing after individual cleanup failures. Cleanup
may remove partial pending control bytes, but never repairs the original request
or result. Any cleanup receipt prevents successful history qualification.
Successful original heal needs no third transition. The controller never writes
receiver fault files through its local filesystem.

Stopped export checks the actual final control-file digest before sealing it into
the existing byte-bound evidence archive. The independent validator requires both
original transitions on all receivers, exact service/configuration identities,
retained guest request/results, the controller ACK barriers and healed final state.
The delivery, service, message/clock, physical-authority, token, query and resource
validators still run at the original and relocated locations. Missing partition
bindings or receipt files cannot fall back to an earlier evidence path.

## Local gate and remaining boundary

```bash
scripts/verify-v52-phase6-remote-partition.sh --skip-build
```

This optional gate uses the existing current Java packages, compiles helpers afresh
and creates a private loopback sshd. It deliberately loses one completed cut reply
and one completed heal reply, retaining the prior upload/bootstrap/voter-launch/
update reply-loss exercises. A heartbeat reports the current stage every minute.
The complete original M04 history runs once; mutations affect disposable evidence
copies only. All owned installer, service, JVM and SSH processes must stop.

Only lightweight controller/guest regressions join the existing CI measurement
test step. Production Java, POMs, workflow topology, formal workload parameters and
release contracts remain unchanged. Receipts retain `qualifiedMeasurement=false`,
`fullRemoteQualification=false` and `paidCloud=false`. The Python checkout is still
shared and all three voters are on one Linux host. SIGKILL/retained restart,
independent hosts/clocks, complete owned members, protected full CI and fresh
provider admission remain pending.

Acceptance records are retained under `target/v52-remote-partition/` and will name
the actual source/working-tree fingerprint, original failures and validation scope.

The first real execution, `run.HSJRIy`, is retained as FAIL. Its serial cut and
heal barriers took 1.464 and 1.018 seconds. The cut-to-heal interval was 4.775
seconds; the target entered CANDIDATE and later became LEADER_READY without the
required snapshot observation. This was not accepted or retried as the same
history. Control preparation/concurrent dispatch now removes that avoidable
serial overhead; the frozen runtime election/recovery settings are unchanged.

The subsequent `run.R9oc4H` completed all eight original business calls and the
required follower snapshot, but replay exposed a historical completeness counter:
the shared V5.1 runtime matrix demanded six basis DATA frame observations. This
valid history transferred only the two selected bases (four REPLY/RECEIVED frames).
V5.2 M04 now explicitly requests selected-quorum coverage, requiring a nonempty
selection and at least four frames **after** every selected basis image has been
fully reconstructed, digest-checked and independently selected. The legacy default
six-frame gate and all other callers remain unchanged. Missing selected basis
transfer still rejects at both locations; no traffic or repeated operations are
added to satisfy a counter. This failed replay and its unchanged input remain.

## Retained acceptance

The final complete gate passed at
`target/v52-remote-partition/run.MvR1Zi/evidence/receipt.json` in **106.028 seconds**,
binding base `fafe140e2b44eff1704b3a09e702525b874d7de4` and executed working-tree
fingerprint `efd80aba9c81795cd5997d75f619f506d510928de900f676d0c0af29639130c6`.
The three receivers each received the same 42-file capsule, bootstrapped once and
launched one service/JVM. All four original reads and four original updates passed.
All six receiver transitions were original; the lost cut and heal replies were
queried without another apply. Final cut/heal barriers were 0.640/0.664 seconds.
These finite local observations are not a latency guarantee for other hosts.

Both physical/query/resource replays and all 76 negative rejections passed:
28 original M04, 14 lifecycle, 14 delivery, 18 partition and two missing-selected-
basis checks. Three services and three JVMs stopped; the installer, service socket,
SSH stream/master and temporary daemon cleanup assertions passed.

The unchanged four-frame input from `run.R9oc4H` also passes original/relocated
replay, all 14 original negatives at each location, 18 partition negatives and two
missing-basis negatives at `target/v52-remote-partition/repaired-replay/`. Its source
is retained as originally executed and no workload was rerun for that repair.
A separate check confirms the legacy default still rejects that four-frame input.
Both original failed runs and their receipts remain untouched.

Validation includes all 430 V5.2 Python tests (23 partition tests), 31 affected
V5.1 fault tests and 21 CI suite tests, the documentation contract, changed local
references, shell syntax and whitespace. Existing Java packages were reused;
helpers compiled freshly. No Maven reactor rebuild, 28-history cohort rerun,
GitHub execution or paid experiment occurred. Only acceptance documentation changed
after the final gate. Exact hashes, logs and the complete commit path list are at
`target/v52-remote-partition/validation-summary.json` and `changed-files.txt`.
