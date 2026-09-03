# Immutable `gse-backup (1,0)` byte fixture

Each `.hex` file is the lowercase hexadecimal representation of the exact member
bytes. Tests materialize these bytes only in an isolated temporary directory. The
representations are immutable compatibility inputs; production code must eventually
emit and accept the same bytes without importing the fixture encoder.

Fixture identity:

```text
gse-backup-v1-d1a8b2c947d21af5d3cf2d0b50e80006c0369b9f4e5a0f5e5a427c6e57e18514
```

The manifest byte layout is:

| Field | Encoding |
|---|---|
| magic | unsigned 64-bit big-endian `0x475345424b503130` (`GSEBKP10`) |
| major, minor | signed 16-bit big-endian `(1,0)` |
| backup/source family | unsigned 32-bit byte length plus strict UTF-8 |
| source major, minor | signed 16-bit big-endian `(1,0)` |
| source history | two unsigned 64-bit big-endian words |
| sequence `B` | signed 64-bit big-endian |
| storage/schema/codec identity | unsigned 32-bit byte length plus strict UTF-8 |
| codec version | signed 32-bit big-endian |
| payload member count | unsigned 32-bit big-endian, exactly `2` |
| each payload descriptor | name, unsigned 64-bit size, 32 raw SHA-256 bytes |
| content digest | 32 raw SHA-256 bytes |
| diagnostic creation time | signed 64-bit big-endian epoch milliseconds |
| diagnostic request ID | unsigned 32-bit byte length plus strict UTF-8 |
| manifest checksum | unsigned 32-bit big-endian CRC32C over all preceding bytes |

Payload descriptors are sorted by unsigned UTF-8 member-name bytes. The exact content
preimage and independent parser are in `scripts/v41/backup_format.py`.
