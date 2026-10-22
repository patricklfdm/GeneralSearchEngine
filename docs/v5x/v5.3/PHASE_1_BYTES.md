# Phase 1 byte-format foundation

Status: **syntax codec locally qualified**. The subsequent
[context/transfer foundation](PHASE_1_CONTEXT.md) is separately qualified;
complete frozen-source capsule/selection work remains pending.
This is part of Phase 1, not its closure and not durable runtime qualification.

## Implemented byte boundary

`MembershipFormat` is an internal 1.3 codec for all 24 storage and 21 wire kinds.
Its packaged schema is the exact canonical projection of the reviewed
[format catalog](format-catalog.json); tests separately retain the independent
[golden bytes](byte-fixtures.json). This adds no public API or active transport.

- Check fixed header, major/minor, kind, zero flags and per-kind unsigned length
  before reading/allocating the payload. Refuse 1.1/1.2 without negotiation or writes.
- Verify checksum, canonical ASCII JSON, exact fields/types and schema array bounds.
  Count object keys in the 65,536-token budget and reject depth above 16 before
  recursive JSON parsing. Duplicate keys, floats, alternate encodings, invalid
  UUID/host/path/base64 and out-of-range scalar values are refused.
- Return immutable decoded maps/lists and copied byte arrays. Distinguish the ROOT
  embedded checksum from hashes of whole framed records.
- Encode all nine new control payloads exactly. BARRIER is empty bytes; DATA keeps
  its inherited opaque application bytes for the later application decoder.
  The V5.2 read token remains byte-for-byte unchanged.

The existing strict JSON implementation is shared only inside production. The
Python checker uses its own framing, JSON, schema and checksum implementation;
it does not import or call the Java decoder to decide correctness.

## Local evidence

- 23 focused Java tests passed, including all 45 golden frame kinds, nine command
  payloads, unchanged token, header-before-body refusal, older minor rejection,
  parser limits and the previous declarations/API/version-boundary checks.
- Nine independent format Python tests passed. The fresh Java byte producer output
  passed independent exact-byte and decode checks for all 45 frames.
- Current 5.3 shared-build prerequisites additionally require the executed
  `V53FormatTest`; old coordinate requirements and cloud allowlists remain unchanged.
- Logs and original Java byte output: `target/v53-phase1-bytes/`.

Syntax fixtures intentionally contain values that are not authenticated authority.
Passing framing/schema checks does **not** prove voter identity, majority, original
source binding, parent force, application correctness or durable publication.
The [context/transfer foundation](PHASE_1_CONTEXT.md) adds exact phased records,
catalog checks, bounded transfers and physical fixture replay. Complete original
basis/capsule selection and durable ownership integration remain required.
The new runtime remains disabled.

```bash
mvn -o --batch-mode --no-transfer-progress -f reactor/pom.xml \
  -Dtest=V53FormatTest,V53DeclarationsTest,V53PublicApiInventoryTest,V51VersionBoundaryTest \
  -Dsurefire.failIfNoSpecifiedTests=false package
python3 -m scripts.v53.format_qualification target/v53-bytes/run-UNIQUE
python3 -m unittest scripts.v53.test_format_fixture scripts.v53.test_format_qualification
```
