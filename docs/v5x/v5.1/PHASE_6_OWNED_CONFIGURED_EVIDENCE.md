# V5.1 Phase 6C3C18 — owned configured physical evidence and backup

**Status:** accepted through PR #249 / master
`7273f00ce8f291797c2d74cd9d830b4f993aaceb`, exact-master CI
[36523283002](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36523283002)
attempt 2, all 27 jobs, including the owned configured history/backup step.
Attempt 1's automatic-healthy rich shard failure remains recorded; retry success
does not establish its cause. The subsequent unified healthy integration is
tracked separately in [6C3C19](PHASE_6_OWNED_THREE_MODE.md).

## Execution boundary

Extend the accepted [configured healthy control](PHASE_6_OWNED_CONFIGURED.md) with
`--physical --backup`. All three voters start before exactly one node-1 activation.
Keep the 90-call frozen experiment tape, 300-second mode ceiling, 30-second status
observation bound, 600-second preparation/collection budgets and 720-second owned
CI step. Status polling observes the configured `READY` state and committed index;
it does not issue additional writes, reads, catch-up or activation.

After the last window, take one public backup while the issuer is live. Stop every
started voter once; only after all stops succeed, restore the backup in a separate
published V4.4 JVM. The [accepted backup protocol](PHASE_6_OWNED_BACKUP.md) keeps
forced once-only claims, original command IDs, reply-loss queries, bounded files,
separate process identity and original deadlines. Uncertainty never permits a new
backup, restore or window execution. Failed evidence and consumed claims remain
collectable; later members still receive stop/collection attempts.

## Independent configured physical inspection

Every guest collects only its own stopped authority under the existing 64-MiB
authority, 128-MiB decoded per-member trace and bounded binary-part limits. Joint
qualification requires exactly three matching mode/source/bundle/attempt configs,
one node-1 issuer, 90 calls and identical manifest/genesis bytes. V4.4 singleton
evidence remains logical-only and cannot request this scope.

Read retained 1.1 bytes without reopening a copied authority with Java. Validate
the frozen manifest topology, configured leader, codec/schema, rich seed corpus,
node owner, bootstrap plan/receipt/preparation, initial markers and complete
healthy root inventory. Compare sealed authority/materialization paths to the
original configs, never to the download path or collector inode. Each receiver's
filesystem-bound bootstrap receipt may differ; common manifest/genesis must agree.

Reuse the existing configured physical oracle for entry/proof ancestry, actual
durable-force quorums, correlated peer ACKs, proof-before-publication and
publication-before-client-success. Additionally bind every observed force to the
same member's retained journal bytes and every client invocation/result to its
original JVM exchange. Project application states independently from retained
entries. The serialized GET/QUERY must match the already published prefix at
invocation and response. This is the published V5.0 read behavior: it has no V5.1
per-read NO_OP or automatic capture/release events. The expected healthy history
contains 73 chosen entries, 72 mutations and final application sequence 76.

The backup response must bind to that published sequence and original trace.
Independently decode all three actual V4 backup files and compare the separate
published restore's complete documents/indexes/sequence. A per-member logical
receipt never claims joint physical completion. Only the joint result can set
`physicalHistoryQualified=true` and `backupRestoreQualified=true`.

## Negative qualification and acceptance

Validate the original physical evidence before mutation. Ten negatives require
exact rejection reasons: missing/changed invocation, changed result identity,
failed original response, changed sequence, resealed read answer, foreign force,
missing publication, missing leader proof and missing remote proof ACK. Invalid
original evidence cannot count as successful negative qualification. Existing
backup byte, receipt, restored-state and process-identity negatives remain active
for both replicated modes.

The existing owned configured CI step adds both flags without changing the job
graph, artifact name, upload policy or Required dependencies. It exercises original
activation/window/backup/restore reply loss through authenticated SSH and three
native-UID mount views. Portable local SSH replay is useful but does not establish
that protected filesystem isolation. Local receipts and retained failure logs live
under `target/v51-configured-evidence`; protected acceptance is recorded above.

No Java runtime, POM, published artifact pin or frozen workload parameter changes.
Provider/account/block observations remain modeled. `fullRemoteQualification=false`
and `paidCloud=false`; complete three-mode preset integration, owned fault cells,
native IAP, trusted preflight and separate V5.1 cloud workflows remain open. Paid
execution still requires exact-request confirmation and user-triggered dispatch.
