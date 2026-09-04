# V4.2 Phase 1 logical migration fixtures

These canonical JSON bytes freeze the independent logical source, target, backup and
plan model used before production format `1.1` exists. They are not production
`gse-durable (1,1)` or `gse-backup (1,1)` member bytes.

`source-v1.0.json` references the published V4.1 physical format contract. The `1.1`
fixtures deliberately carry `physicalEncodingStatus=PHASE2_PENDING`; Phase 2 must
replace or supplement them with exact independently parsed metadata, checkpoint,
manifest and WAL bytes and their immutable hashes. Removing that marker in Phase 1
would falsely claim that the physical format is already frozen.

`fixture-checksums.sha256` binds every JSON member. The independent Python validator
rejects extra/missing members, checksum changes, malformed formats, non-canonical
record order, a changed logical projection, or premature physical-format claims.
