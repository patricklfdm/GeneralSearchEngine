# V4.3 exact `(1,2)` physical fixtures

This directory freezes one independently encoded `gse-durable (1,2)` store and its
canonical-only `gse-backup (1,2)` bundle. The live fixture has four empty but complete
derived components—equality, range, prefix, and `gse-simple-v1` text—bound to one
authoritative checkpoint. The backup contains exactly metadata, checkpoint, and
manifest; it deliberately contains no derived member.

`fixture-inventory.tsv` binds each logical member to a lowercase-hex file and its
whole-file SHA-256. `fixture-identities.properties` freezes the format-profile,
derived-catalog, and backup-content identities. The independent encoder/parser is
`scripts/v43/derived_format_v12.py`; production code is not imported or invoked.

Regeneration is a format change, not a routine fixture refresh. Any change requires
review of the magic, byte order, field order, bounds, capability list, digest domains,
member names, hashes, and published-4.2 fail-closed boundary.
