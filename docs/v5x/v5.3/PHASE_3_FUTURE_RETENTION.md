# Phase 3B — native durable future-target intentions

Status: **LOCAL COMPONENT QUALIFIED**. This local transaction is the next part of
the [offline-survivor requirement](PHASE_3_SURVIVOR_RETENTION.md). It does not yet
authorize network dispatch or complete Phase 3. The original shared limits remain
unchanged; no public membership runtime is enabled.

## Exact local transaction

`retainFutureDispatch` accepts only this live native owner's
[pending-publication capability](PHASE_3_PENDING_PUBLICATION.md). It records an
exact original certificate/application target plus one or more permanent peer
identities whose previously known endpoints must remain possible. Certificate
witnesses are not inferred recipients. An identical call preserves the revision;
an unresolved different target is refused.

The private `future-retention.gsft` container has one candidate,
`future-retention.next.gsft`. Proof and intentions share the same atomic rename,
so a durable intention cannot refer to an incompletely installed separate proof.
Both files share the existing 32 MiB JOURNAL reservation with the original grants,
votes, peer ledger and application metadata. No extra application image is copied.

This is a new internal local container, not a new catalog/wire frame. Its maximum
size is 3 MiB including a 44-byte header: big-endian magic `GSFT`, version 1.3,
total length and SHA-256 of the body. The body contains a length-prefixed canonical
JSON metadata record (at most 128 KiB), a record count, then length-prefixed original
frames in this order:

| Original | Maximum bytes |
| --- | ---: |
| SELECTOR | 4,096 |
| PROMISE | 8,192 |
| SELECTED | 65,536 |
| ENTRY | 16,384 |
| ACCEPT | 8,192 |
| PROOF | 16,384 |
| CERTIFICATE | 16,384 |
| CATALOG | 2,097,152 |
| CHECKPOINT | 16,384 |
| CHECKPOINT_ACK | 2,048 |

Metadata has exactly `root`, `owner`, `revision`, `previous`, `parent`, `peers`.
The peer list is ordered by node identity; each row has exact `identity` and
`lower` anchor. A pending record has one through six rows and all ten original
frames. Empty state has no parent, peers or frames. Revision zero has no predecessor;
subsequent revisions link the previous entire container digest. Pending state
reserves one further revision for completion under the existing counter ceiling.

The mandatory future-retention open entry initializes empty state only at pristine
genesis with an unused peer ledger. It refuses missing state after progress;
legacy component opens cannot substitute for this entry in the future automatic
runtime. Complete candidates require the exact predecessor. Torn candidates are
discarded because they were never returned as active intentions. The surviving
active file and its parent are re-forced before recovered-owner exposure.

While the published selector still names the parent, reopening verifies the exact
stored native certified vote, complete original applied-end inventory and real
application image. Once the selector covers the target, the authenticated current
ancestry must cover all retained anchors. Neither a stored checksum nor a claimed
remote receipt alone supplies authority.

## Publishing and recovering completion

Before recording a new pending target, admission includes both its full candidate
and space for the ordinary 64 KiB peer-ledger candidate plus an empty completion
record. Candidate bytes consume their reserved completion allowance. Reopening
also checks the combined retained bytes and remaining completion reserve.

Publication first installs the actual covering selector. It then durably merges
old/new peer possibilities into the existing ledger, and only afterward replaces
the future record with empty state. Every intermediate state is recoverable:
repeating the conservative merge cannot discard an endpoint or undo a newer proven
observation. Existing applied-end retirement remains guarded by real publication.
Storage identity changes poison the open file owner; force failures cannot return
a successful intention.

## Qualification and remaining integration

Qualification exercises actual original bootstrap/campaign/certification, native
application, record/reopen, real checkpoint-quorum publication and exact capacity
admission. Fresh JVM halt/SIGKILL tests cover recording and promotion/clearing,
including live ownership-lock probes. The independent reader derives original
bytes and complete interrupted/recovered inventories before applying evidence
mutations. The [source-bound receipt](phase3-evidence/future-retention.json) binds
23 final-source Java tests, 18 new process cases (36 fresh JVMs and nine lock probes),
ten exact evidence negatives and normal/optimized/portable replay. All 658 Python
tests pass normally and with assertions disabled. The separate Java guard and
exact-versus-one-byte-short capacity checks are not relabelled as independent
process replay. Fourteen existing peer-ledger crash regressions and their physical
reader also pass; the prior pending-publication originals replay unchanged through
the extracted first-certificate helper. Earlier compile and worker ACK-ordering
failures remain retained separately from the final successful package.

Current source capture refuses a pending future record before writing a fresh
promise, because immutable BASIS propagation has not yet been implemented. That
guard is temporary integration scaffolding, not the final automatic behavior.
The next work must carry the original proof through selection and carried-entry
recovery, qualify replicated intent quorums for future targets, and connect real
dispatch. Complete offline-survivor continuation, automatic maintenance and all
remaining [3B–3E gates](PHASE_3_ENTRY_PLAN.md) stay open.
