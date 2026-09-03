# GeneralSearchEngine V4.1 Phase 2 checklist

- **Status:** Accepted
- **Scope:** Codec-free read-only structural verification and reporting

## Entry and boundary

- [x] Phase 1 merged through protected PR #94 as `e183face`.
- [x] Exact-master CI run `33717370973` passed on that commit.
- [x] Live format remains exactly `gse-durable (1,0)`.
- [x] No backup writer, semantic verifier, restore or cleanup is implemented.

## Public API

- [x] `verifyStore(Path)` and `verifyBackup(Path)` are public static synchronous
  codec-free operations.
- [x] Status order and report/finding record descriptors match the Phase 1 fixture.
- [x] Findings are bounded, immutable, duplicate-free and canonically ordered.
- [x] Paths normalize before equality; sequences and byte counts reject negatives.
- [x] `DurableOperationException` preserves its frozen reason and optional sequence.
- [x] Javadocs distinguish structural validity from semantic decode correctness.

## Store verifier

- [x] Verification obtains the existing normal V4 exclusive lock and refuses a live
  writer with `STORAGE_IN_USE`.
- [x] No lock or store member is created, rewritten, truncated, renamed or deleted.
- [x] Metadata, checkpoint manifest, checkpoint and WAL use an independent parser.
- [x] History, bounds, indexes, authority, WAL generations and sequences are checked.
- [x] Complete frame CRC32C and final incomplete-tail semantics are checked.
- [x] Payloads are streamed under persisted bounds rather than whole-file allocation.
- [x] Retained and authoritative byte inventories are overflow checked.
- [x] Symlinks, non-regular files, exposed hard links and unknown members fail closed.
- [x] Safe staging/obsolete members are reported but never removed.

## Backup verifier

- [x] The exact three-member `gse-backup (1,0)` inventory is required.
- [x] Metadata, checkpoint and completion manifest structure and CRC32C are checked.
- [x] Payload sizes/SHA-256 and canonical domain-separated identity are recomputed.
- [x] Source history, identities, sequence and checkpoint bound relationships match.
- [x] Missing completion is `INCOMPLETE`; extra or corrupt members are `CORRUPT`.
- [x] Read-before/read-after identity rejects changed-while-read members.
- [x] Verification needs no user codec and allows immutable concurrent readers.

## Classification and evidence

- [x] All six structural statuses use the accepted Phase 0 meaning.
- [x] Unsupported-major and incompatible-minor require intact checksummed headers.
- [x] Definite present corruption is retained alongside missing-member findings.
- [x] Generated live stores and immutable V4.0/V4.1 bytes cover the local matrix.
- [x] Independent Python store and backup parsers remain in the CI gate.
- [x] `scripts/verify-v41-phase2-structural.sh` passes locally.
- [x] Full reactor, exact published compatibility, consumers, release artifacts and
  reproducibility pass locally.
- [x] Phase 2 PR #95 passed CI and merged to protected `master` as `a17ad20`.
- [x] Exact-master CI run `33720179867` passed on `a17ad20d3cd03128abf6c4f7fbeb0b752b523b02`.

Phase 3 live backup is admitted from the exact accepted Phase 2 commit above.
