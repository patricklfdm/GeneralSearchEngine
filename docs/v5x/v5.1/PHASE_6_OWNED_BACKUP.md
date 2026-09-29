# V5.1 Phase 6C3C15 — owned healthy backup and restore

**Status:** accepted through [PR #246](https://github.com/patricklfdm/GeneralSearchEngine/pull/246),
master `2846bbc2758f2336e0ed73dbc45001dfe83d8f6a`, exact-master CI
[36498232963](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36498232963)
attempt 1 (27 successful jobs). Foundation/runtime job `109184259601` passed the
owned Linux healthy history and backup/restore gate. This accepts only the bounded
automatic scope below; full Phase 6 and paid cloud admission remain open.

## Scope and contracts

The [cloud workload contract](PHASE_6_CLOUD_WORKLOAD_CONTRACT.md), frozen
`phase6-cloud-workload-plan.json`, [owned healthy tape](PHASE_6_OWNED_WORKLOAD.md),
[physical evidence](PHASE_6_OWNED_PHYSICAL_EVIDENCE.md), and published V4.4 backup
format and public restore API govern. This is one automatic experiment healthy
cell on the existing admitted services. Provider/block observations remain modeled
fixtures; three Linux mount views and actual loopback SSH are required in CI.

`--backup` requires `--physical --workload` in the owned qualification. The ten
warmup calls and four 20-second windows still contain exactly 90 original calls.
After the last window, the issuing voter receives one auxiliary `backup` command.
The existing public API creates the three V4 backup files and one fresh strong-read
barrier. Bounded status observations then require all voters to reach the leader's
durable cut, including that barrier. No extra timed call is inserted.

The controller stops all three voters successfully before issuing one
`restore-backup` command. The issuer launches a separate JVM through the verified
package's published V4.4 `V51CloudLocal restore` entry and isolated classpath.
It restores into a fresh local directory; it never opens copied replicated
authority. A failed tape, backup or voter stop prevents this restore stage.

## Once-only operations and retained evidence

Both commands accept only empty payloads. Forced claims consume each operation
before its side effect, even if it fails or the original reply is lost. Repeated
requests query the original receipt; a different command ID cannot start another
backup or restore. The existing command, service, setup and topology deadlines
remain in force. The 300-second healthy mode, 600-second validation/retention,
720-second qualification and cleanup accounting are unchanged.

Only the issuer requests `collect {"physical":true,"backup":true}` after stop
and the restore attempt. Other voters retain the C14 physical-only payload.
Its closed backup inventory includes the three exported files, backup/restore
claims and results, and restore stdout/stderr. Before/after inventories reject
changed bytes, symlinks, special files and excess size. The existing binary
archive, member, expanded-byte and decoded-trace ceilings still apply.
Failed operations retain available original claims, output and partial exported
files in that collection; incomplete or failed evidence cannot validate as success.

The validator binds both original controller receipts to retained guest commands,
the backup response to the original JVM exchange, and its exact operation ID,
PID, sequence and outcome to the original physical trace. Backup must follow the
complete tape and precede stop; restore must follow stop and precede collection.
The restore process must have a different PID, successful exit, admitted published
classpath and a lifetime within the original command receipt.

Independent Python decoding checks actual V4 metadata, checkpoint and manifest:
checksums, profile/history identity, member/content digests, sequence, descriptors
and ordered documents must match replay of the 90 frozen calls. Restore stdout
must independently report that same sequence, index count and document corpus.
Inventory hashes or a successful process exit alone cannot establish correctness.

The joint physical oracle explicitly expects exactly one auxiliary backup barrier,
checks its captured/released cut and retains all ten causal/read rejection controls.
The C14 default still expects zero. Only joint success can set both
`physicalHistoryQualified=true` and `backupRestoreQualified=true`; missing backup
evidence cannot fall back to physical-only success. Failed requests, partial
downloads, retention, service shutdown and exact-ID cleanup remain on the existing
owned failure path. `fullRemoteQualification=false` and `paidCloud=false` persist.

## Qualification and remaining work

The existing required owned-bootstrap CI step adds `--backup`. Its transport
wrapper discards the original submission replies for all five windows and both
auxiliary commands, then checks unique command IDs and exactly one issuer-owned
backup/restore submission. It does not resubmit failed or uncertain operations.

Local synthetic tests cover checksummed backup decoding, resealed corruption,
changed documents/cuts/PIDs/classpaths, original receipt and trace binding,
consumed claims after failures, lost replies, and stop-before-restore ordering.
These tests are not Linux engine qualification. Mac validation uses a repository
`TMPDIR` because the production path checks reject symlink ancestors. Linux
`/proc`, independent mount namespaces and the packaged JDK remain CI prerequisites.
Local outputs are retained under `target/v51-owned-backup-review`.
The Mac review passed 89 distinct targeted tests across backup, logical/physical
evidence, owned collection/Runner, isolation and helper delivery, plus contract
links, Python syntax and `5.1.0-SNAPSHOT` version alignment. The initial unadapted
owned lifecycle run's six missing-`/proc` errors remain retained; new lifecycle
fixtures explicitly label their synthetic OS metadata. No Linux gate was run here.

For optional Linux shared-filesystem qualification, use
`guest_package_qualification --healthy --physical --backup`; only the automatic
cell qualifies backup/physical history. This does not replace the owned three-view
gate. The next [configured healthy candidate](PHASE_6_OWNED_CONFIGURED.md) connects
the published V5.0 control. Remaining owned modes/evidence and fault cells, trusted
preflight and separate V5.1 workflows still require qualification. Complete cloud preset,
native IAP/source transport and Phase 6 acceptance remain open.
