# V4.0 storage-format compatibility

## Independent compatibility axis

Java source/binary compatibility and durable storage readability are separate
contracts. Passing Japicmp does not prove old storage opens, and reading storage does
not authorize a Java API break.

## V4.0 format identity

V4.0 creates storage family `gse-durable`, format major `1`, minor `0`, with one random
128-bit history identity. Every authoritative manifest, checkpoint, and WAL generation
belongs to that same history.

All V4.0 patch releases must read and write `(1,0)` without changing its meaning. An
engine rejects another family, another major, or a higher minor unless a future
release explicitly documents and tests a reader. V4.0 performs no automatic format
upgrade, downgrade, repair, or history merge.

## Directory ownership

A new store is created only in an absent or empty directory. An initialized directory
must contain valid engine metadata and known engine-owned names. Unrelated files in a
fresh target and unknown files using the reserved GSE prefix are rejected. Known stale
staging or cleanup remnants are classified by format rules and cannot become
authoritative by filename recency.

Open uses an absolute normalized path and an exclusive lock for the lifetime of the
engine. An existing directory is resolved to its real local path; a symlink as the
configured directory is rejected. A second owner, including one reached through an
alias to the same lock-file inode, fails. The lock is coordination, not evidence that
previously written bytes are valid.

## Authority and generations

The authoritative manifest identifies exactly one checkpoint (or none before the
first checkpoint), its sequence, and history identity. WAL generations are discovered
through their self-identifying headers and must form one unique ordered continuation
after that checkpoint. Checkpoint and generation IDs are monotonic within a history.
Files from another history, duplicate generations, sequence overlap, unexplained gaps,
or manifest/file disagreement fail closed.

Staging files and cleanup remnants have explicit non-authoritative names and states.
Modification time, directory enumeration order, and lexicographic "latest file" are
never authority rules.

## Patch and future evolution

- `4.0.x` may fix code while preserving `(1,0)` bytes and semantics.
- A future compatible reader may add an explicitly documented minor version.
- A meaning-changing layout requires a new major and an offline migration contract.
- Older engines are not required to read a newer format.
- No release may silently rewrite authoritative storage merely by opening it.

Release artifacts include immutable `(1,0)` fixtures for fresh, WAL-only,
checkpoint-only, checkpoint-plus-WAL, incomplete-tail, and corruption cases. An
independent inspection tool validates identity and framing without using recovery code
as its own oracle.

The frozen fixture inventory is
[`v4-format-1.0-fixtures.tsv`](../../src/main/resources/io/github/patricklfdm/generalsearch/durability/v4-format-1.0-fixtures.tsv).
Every member carries its own SHA-256 and Base64 payload. The independent V4 consumer
loads that inventory from the core artifact, materializes its bytes, and opens them
through only the public production API; the Python storage inspector separately parses
the same members from source. Fresh is represented by an empty directory, and the
corruption fixture is required to fail as `CORRUPT_WAL`. Changing any row or expected
classification is a format-contract change, not routine test maintenance.
