# V5.1 Phase 6C3C14 — owned healthy physical evidence

**Status:** accepted through [PR #245](https://github.com/patricklfdm/GeneralSearchEngine/pull/245),
master `d07fe8a5ca27e28ebf1b20c157337ed0f078ea5e`, exact-master CI
[36486236193](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/36486236193)
attempt 1 (27 successful jobs). The foundation/runtime job
`109145734146` passed the owned healthy physical gate on this exact source.
This accepts only the bounded scope below; full 6C remains open.

## Collection and original identity

The [owned probe](../../../scripts/v51/guest_owned_workload.py) accepts explicit
physical qualification only within the existing offline automatic experiment
healthy scope. The ten warmup and four 20-second measured windows still issue
exactly 90 calls, once each. After the tape, bounded status observations wait for
all three durable indexes to reach the observed leader cut; this issues no extra
strong read, activation or mutation. It consumes at most 30 seconds within the
original 300-second mode deadline. Status never substitutes for physical evidence.

All voters stop before collection. `collect {"physical":true}` is restricted to a
stopped automatic JVM and copies only that guest's own authority directory. A
bounded before/after inventory rejects links, special files, changed bytes and
oversized authority. The existing binary part, file, expanded-byte and decoded
trace limits still apply. Each collection's authenticated command receipt binds
its complete inventory, including the authority. Unexpected neighbouring authority
and unrequested collection files are rejected even if the inventory is resealed.

The [joint validator](../../../scripts/v51/guest_physical_evidence.py) requires
exactly node 1, 2 and 3, one issuing voter, identical source/bundle/attempt/topology
bindings and identical manifest/genesis bytes. Each logical member validator runs
independently first. A temporary inspection tree contains only inventory-checked
copies of those downloaded bytes. The independent storage inspector checks each
bootstrap seal against its original admitted absolute path from the controller
config. Inspection never starts a JVM on copied authority or changes a seal.

## Joint history oracle

The existing physical oracle replays original forced records, frozen election
bases, wire replies, quorum proofs, publication snapshots and retained prefixes.
It requires every retained voter to include the final chosen durable cut and
checks the frozen V4.4 source corpus. Each successful mutation must have its own
publication between invocation and response. Each successful GET/QUERY must have
one fresh invocation-bound barrier, validated capture and release; its answer is
recomputed from that exact captured application. Per-node ordering is checked;
timestamps from different machines are never treated as one clock.

This scope has no backup command. The read oracle explicitly expects zero
auxiliary backup barriers here, while all existing rich/full-preset consumers
retain their default requirement of one. Neither a missing public read barrier
nor an unexpected backup can pass by changing the expected count implicitly.

The unchanged original must pass before ten causal/read mutations are replayed.
Missing/borrowed read invocation, unknown read identity, changed cut/release,
missing release, resealed wrong answer, missing leader force, missing proof ACK
and failed original result must each fail for its exact expected reason.

Only the complete joint validator can set `physicalHistoryQualified=true`.
Per-member logical receipts retain false. Missing/corrupt collection or physical
failure cannot fall back to logical-only success; the Runner still retains failure
evidence, stops services and performs exact-ID cleanup under existing accounting.
`fullRemoteQualification=false` and `paidCloud=false` remain mandatory.

## Qualification and remaining work

The required owned-bootstrap CI step adds `--physical` without changing its
720-second limit, artifact name or Required graph. It exercises three native-UID
mount views, authenticated packages/source, local seals and the same lost-reply
controls as C13. Provider/block facts remain explicit fixtures.

For local validation, `guest_package_qualification --healthy --physical` exercises
real loopback SSH and all three modes (270 calls), qualifying physical history
only for the automatic cell. Its shared local filesystem does not replace the
protected three-view gate. Synthetic tests separately cover owner/path/inventory
binding, changed seals, live capture rejection, exact auxiliary scope and failed
physical admission. Retain local validation under
`target/v51-owned-physical-evidence`; local results never replace protected
exact-master acceptance.

The next [6C3C15 candidate](PHASE_6_OWNED_BACKUP.md) explicitly adds backup/restore;
the accepted C14 zero-backup scope above remains available and unchanged.
Then connect other modes and faults, followed by trusted preflight
and separate V5.1 cloud configuration/workflows. Native cloud identity, IAP, paid
admission and complete preset qualification remain open. The user still confirms
and triggers paid runs manually.
