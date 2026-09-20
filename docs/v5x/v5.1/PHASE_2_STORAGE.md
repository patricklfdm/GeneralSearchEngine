# V5.1 Phase 2A sealed root-ledger authority

**Status:** implementation and local validation; protected acceptance pending.
**Scope:** storage authority only. No automatic election, application publication,
public bootstrap or service-readiness result is produced by this batch.

## Production implementation

The package-private `AutomaticRecords`, `AutomaticAdmission` and `AutomaticStore`
classes are separate from configured-mode decoding/admission. The canonical JSON
primitive is shared; automatic framing explicitly requires GSER 1.2. The supported
subset is MANIFEST, NODE, JOURNAL, PROMISE, ENTRY, PROOF, READY, GENESIS, PLAN,
PREPARED, RECEIPT, SEAL and ACCEPT. Tests compare every supported schema and its
encoded bytes to the frozen independent fixtures. Other automatic record kinds
remain unsupported here, and old storage versions reject.

The store opens only an existing directory with the ten required root files. It
verifies the expected manifest and local voter, exact all-three plan/receipt/seal,
genesis and ready binding, and the sealed authority path. Missing files, symlinks,
copied seals, unknown files or generation state reject without repair. Public
automatic bootstrap/build entry points retain their Phase 1 disabled guards.
As in the configured store, network/FUSE and volatile filesystems are rejected.

### Initial inventory convention

Each PLAN target's `files` array is sorted by relative filename and contains the
eight initial root files, excluding `bootstrap-prepared.gsr` and `bootstrap-seal.gsr`.
Every row contains exact length and SHA-256 of the full initial bytes. PREPARED's
`inventoryDigest` is SHA-256 of that array's canonical JSON. Each local PREPARED is
byte-identical to its member of the all-three receipt. This binds the existing
catalog's inventory fields without a circular plan/preparation hash.

`replica.lock` is empty. Initial `promises.gsr` is its JOURNAL header plus the genesis
PROMISE (epoch 1, absent proposer, zero incarnation). ACCEPT and PROOF ledgers begin
with their JOURNAL headers only. On restart, these sealed initial ledger bytes must
remain an exact prefix; metadata must remain byte-identical. All three preparation
inventories are checked, while only the local directory's bytes are read.

This is a local sealed-authority check, not cryptographic proof that a remote voter
forced its preparation. The future public bootstrap coordinator owns that obligation.
Test-only initializers create storage fixtures with a projection of application
genesis; they are not independently validated V4 backups or enabled public bootstrap.

## Append and replay rules

- PROMISE starts at genesis and strictly increases; a same-epoch retry must preserve
  proposer/incarnation and exact bytes. Proposer rank is checked against manifest order.
- ACCEPT binds an existing retained promise and immutable ENTRY. New slots are
  contiguous, and the preceding slot needs a local proof before the next acceptance.
  A higher acceptance ballot can carry identical ENTRY bytes, including its original
  origin ballot. A changed value remains rejected until Batch B selection exists.
- PROOF requires an exact local acceptance ballot/value, distinct ordered admitted
  voters, correctly recomputed ACCEPT_ACK receipts and the entry predecessor. Proof
  slots are contiguous; NO_OP/control entries do not advance application sequence.
- Successful storage calls return after `FileChannel.force(true)`. Exact retries
  re-force without appending. Proof ACK hashes bind the full proof record. These are
  storage receipts; they do not represent a public mutation Future or publication.
- A failed write/force makes the handle unusable. Reopen independently scans all
  retained authority. A torn required record rejects and is never trimmed/reset.
  A complete unforced row surviving process death may be recovered conservatively;
  halt/SIGKILL does not simulate loss of an OS page cache or storage power failure.

The directory lock stays owned until close. Record bytes are copied before admission
and writing; returned record values are immutable. Retained-byte limits include all
root files. Replay reads one frame at a time and indexes disk offsets instead of
retaining payloads for the entire history. Limits are 10,000 promise rows, 1,000,000
slots and 1,010,000 acceptance rows (one new row per slot plus bounded re-proposals).
Capacity rejection occurs before writes and leaves an otherwise healthy handle usable.
Local byte limits may be tightened but cannot exceed the limits in the sealed plan.

Local bytes alone cannot identify a completely self-consistent rollback of an entire
disk image. This gate detects incomplete/conflicting retained authority; peer-based
reconciliation and disk-loss quarantine remain later protocol obligations.

## Evidence and validation

[The verifier](../../../scripts/verify-v51-phase2-storage.sh) runs after reactor
package in CI and retains `target/v51-storage` even on failure. The process worker
loads production code from the current-version JARs; fixture setup and fault controls
remain test classes. Evidence records source/diff/inventory hashes, candidate JAR
hashes, actual PIDs/exits, force/ACK events, pre-reopen archives and final agreement.
Force events must reference complete retained record bytes; returned receipts are
independently recomputed against those records and the observed voter/process.

The [independent inspector](../../../scripts/v51/storage_inspector.py) imports neither
production code nor the fixture encoder. It checks real retained bytes against the
written authority rules before any product reopen. Negatives remove force events,
change their process/record identity, remove retained grants/acceptances, introduce
complete conflicting records, append partial records or copy sealed directories.

The crash matrix is 3 ledgers × 6 cuts × 2 termination methods = **36 cases**:
before write, partial write, complete write, force complete, before ACK and after ACK;
worker-owned halt and controller-owned SIGKILL. Each has three concurrently owned
storage JVMs. Only the target is killed; the other owners close normally. Setup of
proof cases obtains real forced acceptances from the test voters before the proof
cut. This is not a network or autonomous failover qualification.

Java tests cover all 13 supported fixture records, receipt/payload/rank/schema
negatives, ownership, exact retries, partial I/O, corruption, finite capacity and
re-proposal with preserved origin. Inherited V5.1 foundation, V5.0 behavior and package
checks stay enabled. See [remaining phase obligations](PHASE_2_CHECKLIST.md).
