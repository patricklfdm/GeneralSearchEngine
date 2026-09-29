# V5.1 Phase 6C3C16 — owned published V5.0 configured healthy control

**Status:** accepted through PR #247 at master
`dfae45670330ffe2a3974982bcc020c534861309`, exact-master CI
[36505526404](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36505526404)
attempt 1 (all 27 jobs), including the owned configured Linux workload gate.
This slice does not complete the experiment preset. Its implementation was based
on accepted PR #246 / master `2846bbc2758f2336e0ed73dbc45001dfe83d8f6a`.

## Scope and governing contracts

The [cloud workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md), frozen
`phase6-cloud-workload-plan.json`, [owned startup](PHASE_6_OWNED_SERVICES.md),
[source producer](PHASE_6_SOURCE_PRODUCER.md), [owned healthy tape](PHASE_6_OWNED_WORKLOAD.md)
and checksum-pinned published V5.0 configured-leader API govern. Provider, account
and block observations remain modeled. The existing delivered package, published
JAR identities, receiver-local bootstrap and three independent Linux mount views
are used unchanged.

The owned qualifier accepts `--mode published-v5.0-configured` only with the full
authenticated source/bootstrap workload path. The default automatic mode retains
its accepted C13–C15 behavior. `Probe` and `Runner` require the explicit
`owned-configured-healthy-experiment` scope, matching mode, original experiment
request and matching startup services. A configured result cannot borrow the
automatic scope or become a full-preset completion. Published V4.4 owned control
is not admitted by this new scope.

## Activation, original calls and cleanup

All three configured voters start before the controller submits exactly one
`fault {"action":"activate"}` to node-1, the frozen configured leader. The guest
calls the packaged public `activateConfiguredLeader` API. A successful original
receipt must precede warmup; cached status and election observation cannot replace
activation. The controller does not search for another leader or retry activation
with a new command ID after failure, disconnect or uncertainty.

The original activation command is limited to 30 seconds inside the unchanged
300-second mode ceiling. Lost replies query the same durable command receipt under
the original deadline. An unresolved or failed activation ends the tape, retains
the original intent/failure and still attempts each started voter's stop once,
collection, service shutdown, retention and exact-ID resource cleanup.

After activation, node-1 issues the ten warmup calls and four frozen 20-second
windows, 90 calls total. Both passive voters configure each matching window. The
existing live-collection refusal remains required. Preparation stays within 600
seconds, collection/validation/retention within 600 seconds, and lease, cleanup,
cost reservation and immutable accounting limits are unchanged. This is one
mode's bounded qualification; the other modes do not receive its unused budget.

## Independent evidence and scope limits

The controller retains exact package-manifest bytes, member configs, original
request/receipt pairs, binary parts and per-member validation. The existing
independent validator binds each JVM to its published core/replication artifacts,
original process, frozen plan, window arrivals, original results, application
sequence, logical answers, sampling boundaries and closed collection inventory.

Configured active evidence additionally requires exactly one original node-1
activation before the first window. Passive voters must have no activation.
Missing, duplicate, late or borrowed activation fails even if the command-store
and archive hashes are resealed. The activation response must still match the
original JVM exchange and its controller receipt, and every JVM operation remains
accounted for. All three stopped members and exactly 90 calls are required.

`physicalHistoryQualified=false`, `backupRestoreQualified=false`,
`fullRemoteQualification=false` and `paidCloud=false` remain explicit for this
original logical-only scope. The [C18 physical/backup candidate](PHASE_6_OWNED_CONFIGURED_EVIDENCE.md)
now adds explicit configured validation flags. The accepted automatic joint history/backup gate still runs
separately and cannot be substituted by this logical control result.

## Qualification and remaining work

The foundation/runtime lane adds a separate 720-second configured owned gate after
the automatic gate. It uses fresh roots, modeled admission, the same authenticated
SSH package/source delivery and three native-UID mount views. Original activation
and all five window submission replies are discarded. Exact command IDs must be
unique, with one node-1 activation and no backup/restore submissions. Existing
producer/download/bootstrap reply-loss, package, stop and cleanup controls remain.
An always-retained `v51-owned-configured-${{ github.sha }}` artifact keeps successes
and failures without changing the Required dependency graph or automatic gate.

Synthetic tests exercise configured admission and mode binding, activation order,
lost and uncertain replies, failed cleanup paths, resealed activation negatives,
the actual owned collector with full 8-MiB parts, and automatic compatibility.
Synthetic OS identities do not qualify Linux processes. Mac review outputs live
under `target/v51-owned-configured-review`; protected three-view execution remains
required regardless of local tests.

The local review passed 127 functional/evidence regressions, 28 controller/budget
tests with explicit synthetic Linux process metadata, and 59 CI/tooling tests.
Workflow YAML and all 142 shell blocks parse; existing steps and Required
dependencies remain unchanged. The contract validates 72 documents and 520 local
links; all changed documentation links also resolve. The initial deadline-fixture
assertion and Mac-only Runner failures remain in the review directory. Both the
accepted master Runner and this candidate fail on the same absent `/proc` path
without modeling; no production deadline or process check was relaxed.

The accepted [published V4.4 owned healthy control](PHASE_6_OWNED_V44.md) connects
the single experiment issuer. The [configured physical/backup candidate](PHASE_6_OWNED_CONFIGURED_EVIDENCE.md)
still requires protected acceptance. Fault cells and complete experiment/preset
or native IAP admission, trusted preflight and V5.1 cloud workflows remain open.
Paid execution continues to require its separate exact-request confirmation and
user-triggered dispatch.
