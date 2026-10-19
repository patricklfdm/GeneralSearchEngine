# V5.2 Phase 6AG SSH voter lifecycle and evidence export

This stage extends [per-voter SSH streams](PHASE_6_SSH_VOTERS.md) with a fixed
SSH control entry for service configuration, original launch observation and
stopped evidence export. Receiver artifacts, helper compilation, the immutable
seed and public bootstrap are still prepared locally. All three receivers share
one Linux host and checkout. This does not qualify package delivery, three-host
execution, independent clocks or cloud admission.

## Ownership and failure handling

`remote_voter_guest.py` accepts only closed lifecycle actions. Preparation checks
the existing private receiver directory's boot, UID, device and inode, exact
source/Java/artifact/helper bindings and untimed local topology before launch.
It creates the service configuration and private Unix socket location remotely.
No caller-provided executable, shell, PID, package installer or replacement voter
is accepted. Public operations continue over the existing persistent SSH relay.

A forced immutable launch claim precedes process creation. An existing claim,
partial publication, failed spawn or absent original worker never permits another
launch. The controller submits once. Only a lost/uncertain transport response may
query the original launch; host-key, authentication, source, malformed-request and
other permanent failures stop immediately. The qualification deliberately drops
one launch reply and later drops one completed update reply. Neither recovery
resubmits an operation or changes its original ID, Future or recorded outcome.

The guest retains the service's exit record. Successful collection requires its
original service and JVM identities to be absent, a successful STOPPED journal
and matching exit record. The controller no longer uses a local `Popen` handle to
infer remote ownership. Failed cleanup sends SIGTERM through a Linux pidfd only
after checking boot/PID/start ticks both before and after opening the descriptor.
This cannot target a replacement process that reused the numeric PID. Interrupted
or failed shutdown remains failed evidence; it is never turned into a successful
export. Lost contact can prevent cleanup confirmation and is reported as failure.

Each SSH exchange and service transition observation is finite. There is no new
whole-history elapsed-time ceiling or business retry. Original API, frame,
operation-count, journal and SSH channel limits remain intact.

## Stopped byte collection

The guest exports only the selected node's authority, traces and control files.
It rejects symlinks, non-regular files and hard links; collection is bounded to
4,096 files and 64 MiB of expanded input/compressed output for this untimed stage.
These are decoding/resource bounds, not changed workload or phase budgets.

An immutable collection manifest binds the configuration, terminal identities,
file sizes and hashes and final archive digest. Downloads use fixed 512 KiB chunks
with exact offsets, archive identity and lengths. The controller checks the whole
archive hash, uses the existing closed USTAR extractor, and compares its complete
inventory before any physical replay. A partial export/download is retained as a
failure; it does not reexecute the history.

Controller channel records and export receipts are added to the downloaded copy.
The mandatory lifecycle validator correlates them with the original service
records and every exported byte. Both original and relocated physical/query
replays retain their existing checks. Removing the lifecycle binding or receipt,
changing the exit owner, adding/missing a file or refreshing the outer inventory
cannot bypass these checks. Independent message/clock-domain checks remain;
there is no cross-host clock inference.

## Optional local qualification

With unchanged current Java packages and the existing local OpenSSH prerequisites:

```bash
scripts/verify-v52-phase6-voter-lifecycle.sh --skip-build
```

The gate creates a private sshd with temporary keys, three service owners and
three JVMs. It runs the complete original candidate-minimum untimed history,
requires exactly eleven reads and three updates, recovers the two deliberately
lost replies, downloads all three stopped exports over SSH, and replays original
and relocated physical/query evidence. Additional lifecycle corruption cases run
on disposable copies. It emits stage changes and a heartbeat every minute.
Private SSH processes and socket directories are checked after cleanup. No system
sshd configuration, accounts, sudo policy, workflow or provider resources change.
Only lightweight regressions join the existing CI measurement test step.

Receipts retain `localArtifactAndSeedStaging=true`, `remoteServiceLifecycle=true`,
`sshEvidenceDownload=true`, `qualifiedMeasurement=false`,
`fullRemoteQualification=false` and `paidCloud=false`.

Next work is remote artifact/seed delivery and bootstrap, declared crash/restart
and partition ownership for formal histories, independent-host/clock qualification,
complete owned members and protected full CI before fresh provider admission.
The frozen suite and release contracts are unchanged.

## Retained validation

`target/v52-voter-lifecycle/run.16Fuhw/evidence/receipt.json` passed in
61.792 seconds. It binds base `237eb06596182c048096df25ab3ba6bbce73f58b`
and working-tree fingerprint
`1d47a295068c19f4926038b2088d63e8bd9e0f8eda57ce881295e988a9f16e02`.
Three services and three JVMs stopped, the private sshd and SSH clients closed,
and all three private service socket directories were removed. The workload
retains exactly eleven reads and three updates; one launch reply and one original
update reply were discarded and recovered without another submission.

All 24 original physical/query negatives passed at each location (48 total),
and seven lifecycle mutations were rejected at both locations (14 total).
The three SSH exports contain 341 files and
559517 compressed bytes in total.
Original and relocated evidence both pass the mandatory lifecycle validation.

All 385 V5.2 Python tests, including 24 lifecycle regressions, and 21 CI suite
tests pass. Documentation references, changed local links, shell syntax and
whitespace checks pass. The initial successful run `run.jIyK1Z` is retained;
the final run additionally checks the tightened export resource bounds and
cleanup paths. The complete 28-history cohort, Maven reactor rebuild, GitHub CI
and paid cloud experiments were not rerun. Existing unchanged Java packages were
used; helpers were compiled freshly.

The implementation was held unchanged during the final execution. Only the
subsequent documentation acceptance record differs from that executed fingerprint.
File hashes, receipts, logs and changed paths are indexed in
`target/v52-voter-lifecycle/validation-summary.json`.
