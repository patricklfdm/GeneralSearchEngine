# V4.0 Phase 4 checkpoint format

## Authority and naming

Phase 4 keeps the Phase 2 WAL frame format at version `1.0`. It generalizes the
generation header fields already present in that format and adds one checkpoint data
format plus one authoritative manifest format, both version `1.0`.

- WAL generations are `gse-wal-%020d.log`.
- Checkpoint data is
  `gse-checkpoint-%020d-<32 lowercase hex>.chk`.
- Checkpoint staging appends `.staging` to that data name.
- The only authoritative pointer is `gse-checkpoint-manifest`; its staging name is
  `gse-checkpoint-manifest.staging`.

Staging and unreferenced checkpoint data never become recovery authority. All files
carry the storage-history UUID established by `gse-metadata`.

## Checkpoint data

All numeric fields are big-endian. Variable byte arrays use a signed 32-bit length
followed by exact bytes.

| Field | Width |
| --- | ---: |
| magic `GSECHK10` | 8 bytes |
| format major / minor | 2 + 2 bytes |
| history UUID | 16 bytes |
| checkpoint sequence | 8 bytes |
| `nextDocId` | 4 bytes |
| live-document count | 4 bytes |
| index count | 4 bytes |
| each index: kind, field, analyzer | 1 byte + bounded strings |
| canonical slot count, equal to `nextDocId` | 4 bytes |
| each slot: state | 1 byte |
| each live slot: canonical key and document | two bounded byte arrays |
| CRC32C over all preceding bytes | 4 bytes |

Slot state `0` is a tombstone and has no payload; state `1` is live. Slot order and
tombstones preserve internal IDs. The business-key map, live count and `nextDocId`
must agree exactly. Key and document bytes must pass configured bounds, deterministic
codec round trips and schema key identity before state is accepted. Index descriptors
use the Phase 2 built-in equality, range, prefix and simple-text classification; index
postings remain derived and rebuild during open.

## Manifest

| Field | Width |
| --- | ---: |
| magic `GSEMAN10` | 8 bytes |
| format major / minor | 2 + 2 bytes |
| history UUID | 16 bytes |
| checkpoint sequence and data length | 8 + 8 bytes |
| checkpoint CRC32C | 4 bytes |
| exact checkpoint filename | bounded string |
| post-cut WAL generation and first sequence | 8 + 8 bytes |
| manifest CRC32C | 4 bytes |

The post-cut first sequence must equal checkpoint sequence plus one. The named data
file must exist and match its recorded length, checksum, history and sequence. Any
malformed or missing authoritative member is `CORRUPT_CHECKPOINT`; recovery does not
scan for an older candidate.

## Publication and recovery

The writer forces the old WAL, creates and forces the next generation at `C + 1`, and
captures immutable state at `C`. A dedicated daemon serializes and validates that
capture, atomically publishes data, forces the manifest staging file, atomically
replaces the manifest, forces the directory, and only then deletes older WAL and
checkpoint data. Mutation admission resumes on the new WAL before serialization.

Open validates all retained generations in monotonic order. Without a manifest it
performs WAL-only recovery across all generations. With a manifest it loads the exact
checkpoint and replays only later units from the manifest generation onward. The
observable source is `CHECKPOINT_ONLY` when no later frame exists and
`CHECKPOINT_AND_WAL` otherwise.
