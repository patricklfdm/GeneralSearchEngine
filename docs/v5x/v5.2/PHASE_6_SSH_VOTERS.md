# V5.2 Phase 6AF persistent per-voter SSH streams

This stage connects the [independent voter services](PHASE_6_PERSISTENT_VOTERS.md)
to the original controller through three persistent pinned OpenSSH channels.
Each node has its own private SSH master and fixed relay. Node startup, receiver
preparation and file collection remain local. This is not three-host deployment,
remote package delivery or cloud admission.

## One channel per voter, original operations only

`remote_voter_relay.py` is a fixed guest entry that can only connect to an existing
private voter socket. It checks the configuration digest, source/helper bytes,
boot/user/directory identity, original service and JVM PID/start-ticks identities,
and the kernel-reported Unix socket peer. It cannot launch, restart, kill or
replace a voter, and accepts no shell command or arbitrary executable.

`remote_voter_ssh.py` reuses the existing pinned-host, noninteractive SSH policy
and foreground master implementation. Multiplexed channels explicitly disable
fallback connections. One channel carries the complete existing public command
stream and its asynchronous results; no SSH setup is performed per read/update.
Original Futures, operation IDs, controller timing and guest/JVM observations are
preserved. Service records remain bound to the independently validated raw traces.

On loss, the controller may explicitly open a new pinned connection and request
only events after its last observed sequence. Neither the relay nor endpoint
resubmits a public operation. At most four channels may be opened for one original
client; exhausted attempts or malformed/identity/authentication failures fail.
Partial sends remain uncertain. A connection close detaches from the service;
only the original close command owns normal JVM shutdown. Local failure cleanup
continues to target the original child session, not an arbitrary remote PID.

Relay buffers are bounded to 64 KiB in each direction, with bounded cumulative
bytes. Frames, public requests, journals and original API limits keep their prior
bounds. SSH setup/handshake and blocked sends have finite deadlines; the whole
history has no new hard elapsed-time limit. Long validation prints progress each
minute. Private keys and control sockets remain outside retained evidence and
are removed after the local gate.

## Retained transport identity

The immutable `remoteVoterTransport` binding names each node's exact loopback
route, host alias and host-pin digest. No private key or credential-file contents
enter evidence. Each receiver retains its channel configuration, requested cursor,
last observed cursor and terminal observation. The supplemental validator rejects
missing routes, changed pins, gaps, cursor resets, early terminal flags and missing
final STOPPED events. These checks are mandatory inside original and relocated
physical replay whenever transport metadata is present; it cannot downgrade to
the earlier local-pipe evidence path.

All clock comparisons remain within their existing process domains. This stage
adds authenticated transport and message correlation; it does not establish
cross-host replication ordering or qualify independent host clocks. Only loopback
targets and whole untimed histories remain enabled.

## Optional local qualification

After a current unchanged runtime package, on Linux with the existing local
OpenSSH prerequisites:

```bash
scripts/verify-v52-phase6-ssh-voters.sh --skip-build
```

The gate starts a private sshd with temporary keys, three independent services
and three JVMs. It executes the original candidate-minimum untimed history,
discards the first completed update reply and closes that node's SSH connection,
then reads its original result over a new connection. Exactly eleven reads and
three updates must remain. Every original/relocated physical/query negative and
transport check still runs. Services, JVMs, SSH clients, masters and the private
daemon must stop. No machine sshd configuration, accounts, sudo policy or GCP
resources change. Only lightweight tests join ordinary CI; the real probe stays
an optional operator gate.

Receipts retain `localLaunchAndDelivery=true`, `qualifiedMeasurement=false`,
`fullRemoteQualification=false` and `paidCloud=false`. Next steps are remote
preparation/launch/collection ownership, formal-history fault lifecycle integration,
independent host/clock qualification and complete members before protected CI and
fresh provider admission. No frozen workload parameters or release contracts change.

## Retained local validation

`target/v52-ssh-voters/run.1hCqAV/evidence/receipt.json` passed in 59.758 seconds.
The three nodes used two, one and one SSH channels respectively; the matching
private-master counts prove that only the node with the discarded update response
reconnected. Exactly eleven reads and three updates remain. All 24 physical/query
negative cases passed at each evidence location (48 total). Three services, three
JVMs, the SSH clients/masters and the temporary sshd stopped normally.

The actual execution binds base `bccd847e7d0f47d87e80dcf46f19bed0075e1f48`
and working-tree fingerprint
`80414d1819e0cb2f0ce347fe1db4769d227337267e2f9f423c61c0f5859d93c7`.
After that execution, the supplemental checker was tightened to reject a terminal
claim on an empty reconnect after the previous channel already consumed STOPPED.
Both retained original/relocated transport inputs passed the corrected checker;
no public operation was reexecuted for this review. The original executed file
hashes and the later checker/test/doc changes remain separately recorded under
`target/v52-ssh-voters/`.

The unchanged Java artifacts were reused and helpers compiled freshly. The full
28-history cohort, reactor rebuild, GitHub dispatch and paid experiments were not
run. This single untimed qualification cannot stand in for three-host or formal
measured acceptance. The ordinary CI topology and all existing gates remain intact.

All 361 V5.2 Python tests (17 new SSH-stream regressions), 21 CI suite tests,
changed-document links, documentation contract, shell syntax and whitespace checks
passed. Validation summaries and raw file/receipt hashes are retained in
`target/v52-ssh-voters/validation-summary.json`.
