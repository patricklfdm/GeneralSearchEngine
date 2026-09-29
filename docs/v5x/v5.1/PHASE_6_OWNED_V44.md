# V5.1 Phase 6C3C17 — owned published V4.4 healthy control

**Status:** accepted through PR #248, master
`b6c055df306e9e8dbb155924fa4a834fe751e786`, exact-master CI
[36514227052](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36514227052)
attempt 2 (all 27 jobs), including protected owned Linux gates. Attempt 1's V5.0
prerequisite-build failure remains recorded; retry success does not explain its
cause. This slice does not complete the experiment preset.

## Scope and governing contracts

The [cloud workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md), frozen
`phase6-cloud-workload-plan.json`, [owned services](PHASE_6_OWNED_SERVICES.md),
[source producer](PHASE_6_SOURCE_PRODUCER.md), [owned bootstrap](PHASE_6_OWNED_BOOTSTRAP.md)
and checksum-pinned published V4.4 public API govern. The experiment's V4.4 issuer
is node-1. Canonical host rotation and complete three-mode preset integration are
not admitted by this slice.

The owned qualifier accepts `--mode published-v4.4-local` only with authenticated
producer/download, source transfer, bootstrap and workload enabled. The explicit
`owned-v44-healthy-experiment` scope binds Runner admission, service mode and
collected evidence. Automatic and configured scopes remain distinct and retain
their accepted execution paths.

## One issuer within the unchanged resource topology

The controller still admits the frozen three-instance/three-data-volume topology,
checks all startup resources, reserves the unchanged cost and cleans every exact
resource ID. Only node-1 receives the V4.4 package, seed, idle service and workload
JVM. Nodes 2 and 3 do not start local controls or replica processes. The common
topology metadata is retained without introducing a fourth host or reducing the
resource reservation to a single-machine price.

Mode-dependent membership is closed: V4.4 has exactly node-1; configured and
automatic modes require nodes 1, 2 and 3. Wrong, missing, duplicate or mixed-mode
members fail before source preparation. The producer accepts one original
preparation, exports one immutable source descriptor and downloads only that
member's authenticated chunks. Lost preparation replies query the original claim;
bounded immutable reads retain interrupted bytes. Node-2/node-3 export requests
cannot borrow this singleton preparation.

After source transfer, node-1 imports and seals the original source once. Its
bootstrap identity contains only `sourceSha256`, with no replication manifest,
genesis or authority files. The existing receiver consumes partial destinations
and does not repair or replay an uncertain import. Package, mode, source,
descriptor, path and original deadline bindings remain required.

## Frozen calls and independent evidence

Start one published V4.4 JVM, then issue ten warmup calls and four 20-second
windows, 90 calls total. V4.4 needs neither election polling nor configured-leader
activation. Each window uses its original command ID; losing its submission reply
only triggers receipt queries under the original deadline. A failed or unresolved
start/window ends the tape, preserves its intent/failure, and still attempts the
started process's stop, collection, service shutdown, retention and resource cleanup.

The accepted independent guest validator checks the isolated V4.4 classpath and
artifact digest, original process and command receipts, all five windows, fixed
arrivals, original results, logical answers, application sequence, sampling and
closed archive inventory. One stopped active node-1 member must supply all 90
calls. Wrong host, missing windows, altered answers or partial/corrupt archive parts
cannot establish completion. The live-collection rejection remains exercised.

This scope keeps `physicalHistoryQualified=false`, `backupRestoreQualified=false`,
`fullRemoteQualification=false` and `paidCloud=false`. Automatic physical/backup
flags fail before setup for V4.4; logical replay does not claim local storage or
backup qualification. Production Java, POMs, published pins, workload parameters,
300-second mode ceiling and preparation/collection budgets are unchanged.

## Qualification and remaining work

The foundation/runtime lane adds a separate 720-second V4.4 owned gate using the
existing authenticated loopback SSH and native-UID mount-view machinery. It hides
producer exports before receiver import and discards all five window submission
replies. Exactly one service, one source export, five distinct window commands,
zero activation/fault/backup commands and unchanged three-resource cleanup are
checked. Always retain `v51-owned-v44-${{ github.sha }}`, including consumed claims
and failure evidence. The existing automatic/configured gates and Required graph
remain unchanged; these separate runs do not establish one complete preset.

Local review passed 161 functional/evidence regressions, 90 shared controller,
service, bootstrap and package tests with explicit synthetic Linux process metadata,
and 59 CI/tooling tests. Workflow YAML and all 143 shell blocks parse; existing
steps and Required dependencies remain unchanged. Version alignment remains
`5.1.0-SNAPSHOT`. The documentation contract validates 73 documents and 529 local
links; changed Python syntax, whitespace and local documentation links also pass.
Review logs and file hashes are retained under `target/v51-owned-v44-review`.

Mac checks do not establish Linux mount/JVM qualification. Initial Mac temporary
directory and missing-`/proc` fixture failures are retained; resolved temporary
paths and explicitly synthetic process metadata do not weaken live checks.

The next [configured physical/backup candidate](PHASE_6_OWNED_CONFIGURED_EVIDENCE.md) connects those evidence layers, before
complete three-mode preset integration and owned fault cells. Native cloud IAP,
trusted preflight and separate V5.1 workflows remain open. Paid execution continues
to require its separate exact-request confirmation and user-triggered dispatch.
