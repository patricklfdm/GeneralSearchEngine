# V5.1 Phase 6C3C13 — owned automatic healthy workload

**Status:** accepted through PR #244, master
`71ca5d9e52139815a5bd4dfddf330c4d0d9fe800`, exact-master CI
[36462747697](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36462747697)
attempt 1 (all 27 jobs). Its original failed large-part collection and diagnostic
replay below remain recorded. [Physical history](PHASE_6_OWNED_PHYSICAL_EVIDENCE.md)
is accepted through PR #245, followed by [automatic backup/restore](PHASE_6_OWNED_BACKUP.md)
through PR #246; native cloud writes and full 6C remain open.

## Scope and lifecycle

[The owned probe](../../../scripts/v51/guest_owned_workload.py) attaches to the
three services already admitted by [owned startup](PHASE_6_OWNED_SERVICES.md) and
[authenticated source production](PHASE_6_SOURCE_PRODUCER.md). It requires the
original request, authenticated package manifest, three matching service configs
and successful receiver-local public bootstrap before starting any JVM.

The runner accepts this probe only with the explicit
`owned-automatic-healthy-experiment` qualification scope, its matching startup
services and an experiment request. It runs only candidate automatic `healthy`:
10 warmup calls followed by four original 20-second windows, 90 calls in total.
The leader is observed from the actual JVMs. Before each window, both passive
voters configure that same instrumentation window. The leader's existing local
scheduler executes the frozen tape; SSH only submits and observes a whole window.

Every command intent and terminal receipt is forced in controller evidence. A
lost submission reply permits only queries of that same command ID. No warmup,
measurement, activation or mutation is replayed. A failed window stops the tape.
The controller retains partial failure diagnostics and attempts each started or
uncertain JVM's stop once, then collection, service shutdown and exact-ID cleanup.
It never replaces a failed measurement with another successful attempt.

The existing preparation deadline is 600 seconds. The existing healthy stage
and automatic-mode ceiling apply, including a maximum 300 seconds for this mode;
leader observation uses at most 30 seconds within that original deadline. JVM
close, binary collection, independent validation and retention consume the existing
600-second validation-retention stage. Cleanup, total 5400-second topology limit,
cost reservation and immutable ledger rules are unchanged. A collection/retention
failure still enters cleanup and retains its charge; absence of complete retained
evidence prevents releasing the lease. A retained FAIL is never promoted to PASS.

## Independent evidence

The [guest evidence validator](../../../scripts/v51/guest_evidence.py) requires
explicit `healthy=True` for all five windows. It independently checks original
command stores and controller receipts, exact frozen specs, scheduler arrivals,
every JVM request/result and logical state across all 90 calls, process/build
identity, per-member samples, trace identity and closed binary inventories.
Both passive members must have all five configuration exchanges and resource
boundaries. A ten-call warmup cannot satisfy the complete-window scope.

All JVMs stop before collection. The original active-JVM collection rejection
remains a required negative. Collected archive parts, manifests, controller
transcripts, exact package-manifest bytes and validation records are packed for
owned retention; replay directories are derived scratch, not replacement evidence.
Existing collection limits, 2000 JVM exchanges, resource ceilings and per-member
decoded-trace budgets still apply. Evidence reads do not authorize workload retry.

This slice establishes logical healthy-window qualification only.
`physicalHistoryQualified=false`, `fullRemoteQualification=false` and
`paidCloud=false` are explicit. Other modes, faults, physical authority/history,
backup/restore, complete preset semantics, native IAP and real provider/block
identity remain separate requirements. Its modeled ledger completion is not a
paid experiment admission or a completed cloud preset.

## Qualification and remaining work

The existing required owned-bootstrap CI step adds `--workload`. It uses actual
loopback SSH, installed packages, three native-UID mount views at the same sealed
destination, receiver-local seals and automatic JVMs. Provider/disk/account facts
remain fixtures. The exact loopback host mapping is recorded separately from
provider private-address observations; it does not change cloud identity checks.
All five workload submit replies are discarded, then recovered by original-ID
queries, with exactly one submission per command. Earlier package/source/bootstrap
reply-loss and immutable-download checks remain required. The outer 720-second
qualification bound, Required job graph and original artifact retention remain.

The standalone SSH package qualifier supports `--healthy` for all three modes
(270 calls), on shared local paths without sudo. This exercises the package,
transport, scheduler and validator but cannot substitute for the owned three-view
CI gate. Synthetic regressions cover later-window corruption, missing/reordered
windows, passive coverage, reply loss, scope restrictions, failed collection and
cleanup/accounting. Validation receipts are retained under
`target/v51-owned-workload`; corrected-source protected CI is recorded above.

### CI collection boundary correction

PR CI [36451894683](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36451894683),
attempt 2, executed all five owned healthy windows in 113.595 seconds and completed
cleanup within budget. All three member collections then failed with
`binary block limit`: the owned adapter supplied each downloaded archive part as
one receiver block. Archive parts allow 8 MiB; the receiver accepts blocks no larger
than 1 MiB. This is a deterministic adapter error for a part larger than 1 MiB.
The earlier standalone SSH collector already split its input into bounded blocks;
that separate qualification did not cover this owned-path boundary.

The adapter now splits the downloaded bytes into blocks of at most 1 MiB, retaining
the original part length, digest, partial-file and archive limits. Three new owned
collector regressions exercise full 8 MiB parts plus tails through the independent
validator, then verify that truncation and corruption remain failures, retain their
partial bytes and do not skip validation of the remaining members or retry reads.
All three regressions fail on the original collector; 74 related tests pass after
the correction.

Offline replay through the corrected collector of this CI attempt's unchanged
retained archives passes all three members and 90 original calls. It consumes only
original stop/collection receipts and immutable parts; no JVM or window is rerun.
The original failed receipts remain intact. Replay receipts and hashes are under
`target/v51-owned-workload-ci-fix`; this is diagnostic replay, not corrected-source
protected acceptance, which is recorded above.

The [configured healthy candidate](PHASE_6_OWNED_CONFIGURED.md) extends the owned
path to the published V5.0 control. Then integrate remaining owned modes/cells and
configured physical/backup evidence, followed by
trusted preflight and separate V5.1 cloud configuration/workflows. Paid runs still
require exact-request confirmation and manual triggering by the user.
