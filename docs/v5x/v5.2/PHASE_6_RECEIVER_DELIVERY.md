# V5.2 Phase 6AH SSH receiver delivery and bootstrap

This stage connects a closed JAR/helper/seed capsule to the existing
[SSH voter lifecycle](PHASE_6_VOTER_LIFECYCLE.md). The controller creates the source
capsule once, sends it to each receiver through pinned SSH, and observes one
receiver-owned installation and public bootstrap. It no longer copies input files
into a receiver or invokes the receiver's Java bootstrap locally.

The qualification still uses one Linux host, loopback TCP and one already verified
Python checkout. Controller-side package production/helper compilation and private
sshd setup remain local. Python agent deployment, independent hosts/clocks, formal
fault lifecycles, complete measured members and provider admission remain open.
No runtime Java, POM, frozen workload or release contract changes.

## Closed package and original transfer

`remote_delivery_package.py` allows only the declared JARs, compiled consumer and
observer classes, the three immutable V4.4 seed-backup files and the exact topology.
It binds source/checkout/Java identities, input hashes, complete file inventory,
archive digest and each 32 KiB transfer part. The untimed delivery is limited to
512 files and 32 MiB expanded/compressed bytes. Requests keep the existing 64 KiB
bound. These are resource/decoder limits, not reduced workload parameters.

The guest checks the private parent boot, UID, device and inode. Each original
transfer owns an immutable descriptor and numbered forced part records. Changed
parts, gaps, foreign files, partial publications and a changed descriptor fail;
identical completed part bytes may be observed without modifying them. The
controller sends each part once, then queries its original receipt if that reply
is lost. It never restarts the transfer or reissues a public operation implicitly.
Authentication, pin, source and request failures stop immediately.

## One detached bootstrap

An immutable launch claim precedes the detached installer. A partial launch,
failed spawn or missing original executor remains consumed uncertainty. The
worker assembles and verifies the complete compressed archive and its bounded
USTAR inventory before creating the fresh receiver destination. Symlinks, hard
links, PAX/GNU extensions, unexpected files and modified input bytes are rejected.
It invokes only the existing `V52RemoteBootstrap` with a fixed classpath/root/node.
There is no caller-supplied shell command, executable, PID or package installer.

Bootstrap writes a receipt naming its original process, actual receiver directory
identity, loaded JAR paths and resulting manifest/genesis hashes. No voter may
start until that original installer has exited successfully. On failure, the
partial package, destination, diagnostics and consumed launch remain; they are
not repaired or overwritten by a new bootstrap. The existing 120-second bootstrap
subprocess boundary and finite SSH/query observations remain; no new whole-history
time limit is imposed. Long qualification emits a heartbeat every minute.

## Continuity into runtime and retained evidence

The final history binding includes the exact package and all three bootstrap
receipt hashes. Before service start/attachment, the guest checks every installed
input and its original receiver-directory identity. At shutdown, each bootstrap
receipt travels back through the prior bounded evidence-download path. The
retained source capsule is independently scanned during both original and
relocated replay, along with the physical authority, query and message/clock-domain
checks. A missing delivery binding, receipt or package cannot fall back to the
older local-preparation evidence path.

## Optional local qualification

With the existing current Java packages and local OpenSSH prerequisites:

```bash
scripts/verify-v52-phase6-receiver-delivery.sh --skip-build
```

The gate uploads the same package to three initially absent receiver roots,
executes three bootstraps and starts the three persistent voters over SSH. It
deliberately discards one completed upload-part reply and one bootstrap-launch
reply, retaining the prior voter-launch and original-update lost-reply exercises.
Each part, bootstrap, voter launch and public operation must remain original.
The full candidate-minimum untimed history retains eleven reads and three updates,
then all original/relocated physical/query negatives, lifecycle negatives and
additional delivery mutations run. All owned SSH/service/JVM/installer processes
must stop. No system sshd configuration or provider resources change.

Receipts use `sshDelivery=true`, `remoteBootstrap=true`,
`localArtifactAndSeedStaging=false` (receiver inputs are transferred),
`sharedPythonCheckout=true`, `qualifiedMeasurement=false`,
`fullRemoteQualification=false` and `paidCloud=false`. These local receipts do not
replace the complete hosted cohort or future exact-source protected/cloud checks.

## Retained local validation

`target/v52-receiver-delivery/run.lSfccV/evidence/receipt.json` passed in
109.172 seconds. The execution binds base
`29a0801b76e810f21d087ddcee1f36f162c5933a` and working-tree fingerprint
`e4f423033a40bd47234a666bb46f3e41d707b31d32770220cbebefcf4ba96de7`.
The shared capsule has 41 files, 2,229,967 compressed bytes and
69 parts per receiver. Each node submitted every part and its bootstrap
exactly once. The two deliberate delivery reply losses were resolved by query;
the prior voter-launch and completed-update reply-loss checks also passed.

The original history retains eleven reads and three updates. All 24 physical/query
negatives passed at each location (48 total), seven lifecycle negatives passed at
each location (14 total), and seven delivery negatives passed at each location
(14 total). Three bootstrap installers, three voter services and three JVMs
stopped. All owned SSH channels/masters and the temporary sshd closed; service
socket directories were removed.

All 406 V5.2 Python tests (including 21 new delivery regressions), 21 CI suite
tests, the documentation contract, changed local references, shell syntax and
whitespace checks pass. The existing Java packages were reused and helper classes
compiled freshly. The Maven reactor, complete 28-history cohort, protected CI and
paid experiments were not rerun. The implementation was held unchanged during
this gate; subsequent documentation acceptance notes are separately recorded.

Source/file/receipt hashes, logs, changed files and the PR description are retained
under `target/v52-receiver-delivery/`; the index is `validation-summary.json`.
