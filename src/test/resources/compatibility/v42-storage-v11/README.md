# Immutable V4.2 format `(1,1)` fixtures

These lowercase hexadecimal files are the exact Phase 2 bytes for one closed
`gse-durable (1,1)` store and its matching `gse-backup (1,1)` bundle. The live and
backup inventories share byte-identical metadata/checkpoint payloads by design.

`fixture-inventory.tsv` freezes each logical member, SHA-256 and backing hex file.
`fixture-identities.properties` freezes the canonical profile digest and the
domain-separated `gse-backup-v2` content identity. The independent
`scripts/v42/storage_format_v11.py` encoder/parser must reproduce and accept these
bytes without calling production recovery or codecs.
