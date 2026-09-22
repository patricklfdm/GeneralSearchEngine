# V5.1 Phase 4H: public capacity and admission boundaries

**Status:** local qualification passed. Protected Batch H and complete
Phase 4 acceptance remain open. [Batch G](PHASE_4_PUBLIC_RECLAMATION.md) is accepted
through PR #198, master `4833bddf08b95a9cd28d63ee0b1c78e2e3de16dc`, exact-master
CI `35664882661`.

## Public execution and sealed bounds

`scripts/verify-v51-phase4-public-bounds.sh --skip-build` compiles external
consumers against candidate JARs. All bootstrap, runtime startup, mutations,
reads and close calls use public APIs. The observer only records events or holds
an actual read/force boundary. It cannot create authority or elect a leader.

The small fixture seals one pending public client operation, a 128-KiB frame,
four bulk elements and four application documents. Other fixture defaults remain
as recorded by the public bootstrap binding. These are explicit test settings,
not changed public defaults or a performance claim.

## Fifteen cases

| Cases | Required observation |
| --- | --- |
| Pending read / pending write | Hold READ_CAPTURED or ACCEPT_AFTER_FORCE with the single admission permit occupied. Another mutation returns NOT_SUBMITTED/CAPACITY_EXCEEDED; another read returns NOT_APPLICABLE/CAPACITY_EXCEEDED. Release the held call, serve fresh reads/writes, and reopen a retained voter. |
| Payload / bulk / document limit | Reject a 100,000-character document exceeding the sealed frame payload, a five-element bulk, or three new documents after two existing documents. No rejected mutation may reach even one forced acceptance. Later smaller operations and retained restart succeed. |
| No quorum at startup | Start one voter, observe its campaign, and reject read/write calls without peers. Only afterward start two other public JVMs, gain service, acknowledge data and reopen a retained voter. |
| Disk 1.0 / 1.1 headers | Change only the automatic manifest's version header and recompute its checksum. Two independent public startup processes reject the incompatible header and preserve all three voters' exact bytes. These are header-rejection probes, not complete legacy disk fixtures. |
| Group / configuration / schema / bounds mismatch | Use a changed public configuration with the original stopped authority. Two independent starts reject it without modifying authority; a correctly configured handle subsequently starts successfully. |
| Configured on automatic / automatic on configured | Bootstrap each mode through its own public offline API. Attempt the other mode on those genuine candidate-created directories twice, preserve bytes, then start the correct mode. |
| Wire rejection | On a live automatic public endpoint, send seven incompatible frames: 1.0/1.1 header, configured mode, wrong protocol string, wrong group, wrong manifest and an oversized length declaration. Each closes/resets without a response or authority mutation; valid correlated handshakes succeed before and after every probe. |

Six capacity cases each use three voter JVMs and a fourth retained restart. Eight
admission cases each use two independent rejecting processes; six additionally
run a valid public startup control. The wire case uses one public voter with a
bootstrap-bound 600–601.2-second election interval, leaving an explicit quiet
window for exact authority comparisons. Wire probes use three-second socket bounds;
a timeout fails the case. This wire lane makes no failover or timing claim.

For the configured-mode startup probe only, NOT_APPLICABLE is the adapter's
lifecycle label: V5.0's ReplicationException supplies a reason, not the new
automatic-mode outcome API. These candidate-mode controls supplement the existing
separately pinned published V5.0 compatibility lane; they do not replace it.
Configured startup rejects the automatic-only directory member with
INTEGRITY_FAILURE before decoding its manifest. Automatic startup on configured
authority reports PROTOCOL_MISMATCH. Both classifications are checked exactly.

## Independent evidence

Capacity histories run the existing exhaustive client-history and decoded
force/quorum/read oracles. Additional checks bind tiny limits to the sealed
bootstrap descriptor, rejection responses to the actual held boundary, and every
NOT_SUBMITTED mutation to the absence of any corresponding forced acceptance.
Fresh successful writes and strong reads are required after rejection, including
retained restart. The solo-start schedule retains controller-clock JVM launch and
client-response intervals, proving that both peers start after the rejected calls.

Admission probes retain original and faulted inventories, exact archived rejected
authority, separate PIDs, typed outcomes and an inventory after each attempt.
Wire evidence retains sent/received bytes, checksums, exact isolated fault fields,
pre/post inventories and correlated live controls. Negative variants remove real
boundaries/resumed work, fabricate admission success, reuse PIDs, mutate authority,
substitute uncorrelated replies or label a timeout as rejection. They must fail.

CI executes the matrix and always retains receipts, raw traces, client histories,
rejected authority, candidate hashes and source inventory for fourteen days.
All writes are single attempts; rejected and uncertain calls remain recorded.

## Coverage and remaining work

This batch extends E01/E10/E11/E12 with concrete public schedules. It does not
close every resource-exhaustion or compatibility case. Epoch/promise/ancestry and
snapshot-staging exhaustion, saturated payload/control transport queues, slow-force
accounting, conflicting/ambiguous frozen selections and the remaining E01–E12
mapping still require explicit qualification. Full Phase 4 acceptance is separate.
Phase 5, cloud experiments, version changes and publication remain outside this batch.

## Local validation

Base `4833bddf08b95a9cd28d63ee0b1c78e2e3de16dc` plus this batch, 2026-09-21:

- Targeted reactor package: all 16 V51PublicRuntimeTest/V51AutomaticRuntimeTest
  tests passed. This is a targeted regression run, not a new full-reactor test claim.
- Complete fifteen-case gate:
  `target/v51-public-bounds/run.Asqpnq/evidence/receipt.json` — all cases passed,
  with 53 application calls, nine classified client rejections, 47 runtime/probe
  process identities and 77 rejected negative variants. Seven incompatible wire
  probes each retained a valid handshake before and after rejection.
- Shared default configuration regression:
  `target/v51-public-runtime/run.lEOBd2/evidence/receipt.json` — four process
  instances, nine chosen/publications, three successful mutations and three
  strong-read barriers passed, including the published V4.4 backup comparison.
- All 124 V5.1 Python tests passed, including fourteen new rejection-checker
  regressions. All fourteen CI-classifier/required-job tests, CI YAML, shell syntax,
  the 30-document contract and whitespace checks passed.

Candidate JAR SHA-256 values:

- Core: `f9d7408be9c675c9d489a6f517f73d3a738b587ea1f6d87c1bc7d690d0a0395d`.
- Replication: `c43a9088e99929faf8a2b8a7266967c27887a325926be3e1a6916a108a770ed4`.

Exploratory failure receipts remain retained. They exposed driver assumptions:
the common physical oracle requires a retained restart and at least three
acknowledged writes, while the configured-mode inventory check rejects an
automatic-only member before inspecting its format header. The final scenarios
meet those requirements and preserve the existing exact error classification.
The source inventory is captured at execution; this summary is written afterward.
