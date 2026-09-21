# V5.1 Phase 4F: public protocol and recovery fault matrix

**Status:** implemented and locally qualified. Protected Batch F
and complete Phase 4 acceptance remain open. [Batch E](PHASE_4_PUBLIC_RECOVERY.md)
was accepted through PR #196 at `15eb04054f28ecb52b896eedb79775c257736e00`,
exact-master CI `35579584390`; all six jobs and the new recovery/lifecycle gate passed.

## Public boundary and scenarios

Run `scripts/verify-v51-phase4-public-protocol.sh --skip-build` after packaging
current sources. Public bootstrap and separate external consumer compilation use
the candidate JARs. Every group operation uses the public builder/start, addAll,
strong search and close APIs. The observer may block real transport messages or
stop a JVM at an existing storage/transport observation point; it cannot grant
promises, submit internal protocol entries or activate a leader.

| Cases | Required execution |
| --- | --- |
| Competing campaigns | All three isolated voters force their own distinct ballots; none publishes until the network heals. |
| Asymmetric requests / responses | During startup, drop node-1 outbound requests or their returning responses while actual reverse-direction traffic succeeds; heal before requiring service, then reopen a retained voter. |
| Minority discarded / selected | Interrupt after one local ACCEPT force, before any remote ACCEPT. Exclude its disk from the next quorum or include it; independently verify the selected slot and exact final documents. The retained case reaccepts the original entry under a higher ballot. |
| Basis halt / SIGKILL | Interrupt a noninitial frozen-basis chunk reply; retain the source disk, restart publicly and verify subsequent complete selections. |
| Snapshot progress halt / SIGKILL | Interrupt a lagging follower after forcing a partial transfer watermark; verify the retained prefix against actual sent bytes and reopen. |
| Snapshot selector halt / SIGKILL | Interrupt after forcing the selector for a completely transferred snapshot, before its install acknowledgement; verify exact selected snapshot bytes and reopen. |

The eleven cases use real loopback TCP and four or five voter process instances.
Snapshot scenarios initially run a two-voter majority and subsequently start the
third, lagging voter. After the interrupted voter reopens, the original leader
stops: the remaining pair must elect, read and acknowledge another write before
the original leader rejoins. Basis cuts select a follower whose public proven
index already covers the seed history; they cannot silently substitute a tiny
genesis transfer for a multichunk recovery. The fixture freezes 4096-byte chunks through public bootstrap
to exercise actual multichunk transfers with bounded small data. This is a test
configuration, not a change to defaults or a performance claim.

## Independent evidence

The existing bounded client-history checker and separate chosen-prefix/force/read
oracle both run. The latter reconstructs every selected pair from complete frozen
basis bytes, validates entry and proof quorums, and compares captured reads with
the canonical application projection. Scenario-specific checks additionally bind:

- Actual distinct self-campaign promises and directional drops, with observed peer
  execution for lost responses and successful traffic in the reverse direction.
- A minority entry strictly beyond its disk's proven prefix, no original entry
  quorum, later frozen selection, and retention under a higher acceptance ballot
  or supersession at the same slot.
- Exact process identity, requested/observed crash boundary, exit code, retained
  restart, archive hash/inventory and interrupted transfer bytes.

A crash marker must follow its actual exact storage/transport boundary. Snapshot
bytes are bound to the retained transfer ID, recipient and complete ballot. A
marker label or a successful public role hint alone does not qualify either cut.

Negative variants remove forces, replies, selection, crash/restart markers or
transfer prefixes, alongside existing stale/partial/reordered-read and missing-proof
checks. Failed and successful source inventories, JAR hashes, histories, wire/force
traces and pre-reopen archives are always retained by CI for fourteen days.

## Coverage and remaining work

This batch extends E02/E03/E04/E06/E07 through public process execution. It does
not establish all schedules in those rows: conflicting/ambiguous selections,
floor/deletion interruption with two durable sources, capacity/promise exhaustion,
mixed-mode/wire/disk rejection and the remaining E11/E12 mapping still require
their public evidence. Internal Phase 2/3 evidence keeps its original scope.
Phase 5, cloud runs and release remain outside this batch.

## Local validation

Base `15eb04054f28ecb52b896eedb79775c257736e00` plus this batch, 2026-09-21:

- Complete eleven-case gate:
  `target/v51-public-protocol/run.OaWyzN/evidence/receipt.json` — all cases passed,
  with 73 application calls checked by the client-history and physical oracles,
  92 rejected negative variants, and four or five voter JVM instances per case.
  Both minority outcomes and all six halt/SIGKILL recovery boundaries qualified.
- Shared consumer/observer regression:
  `target/v51-public-recovery/run.Zbcfym/evidence/receipt.json` — all ten previous
  recovery/lifecycle cases passed, including separately executed published V4.4
  import and cursor controls.
- All 90 V5.1 Python tests passed, including twelve new checks for transfer
  gaps/overlaps/changed retries, exact crash boundaries and frozen-quorum tail
  selection. CI execution/always-retained artifacts, executable shell/Python
  syntax, the 28-document contract, changed Markdown links and whitespace passed.

No production Java changed in this batch. It uses the accepted candidate JARs
below and does not claim a new full-reactor run:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `2300c45c8f2bb5596d96ffe6479254b50a7fd2f87df81a3ba592c67898c2db4f`.
- Published V4.4 control: `0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5`.

Exploratory failures are retained with their original source inventories. They
identified driver/checker assumptions: an absent tail yields an empty selection
before activation, directed startup need not progress before healing, a stale
genesis image may occupy only one chunk, and a candidate's own basis need not
appear in a PROMISE reply. Final checks bind the actual frozen bytes and exact
cut rather than weakening quorum/force requirements. Snapshot cases additionally
require a subsequent election involving the recovered voter. This summary is
written after execution; protected Batch F and full Phase 4 acceptance remain open.
