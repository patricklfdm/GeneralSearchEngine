## GeneralSearchEngine 5.0.0

V5.0.0 is published and independently verified. It adds optional replication for
one shard with exactly three fixed voters and a configured leader, while preserving
the existing in-memory and single-node durable search APIs.

### Maven Central

- [io.github.patricklfdm:general-search-engine:5.0.0](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/5.0.0)
- [io.github.patricklfdm:general-search-engine-processor:5.0.0](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/5.0.0)
- [io.github.patricklfdm:general-search-engine-replication:5.0.0](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-replication/5.0.0)

### Added

- Quorum-persisted epoch fencing, durable entry and commit proof, and leader-only
  public application access.
- Typed offline bootstrap, resume, cleanup and replacement; sealed public 1.1
  authority; explicit activation, leader reconstruction and follower catch-up.
- Verified replica snapshot transfer, bounded admission, diagnostics, local
  checkpoint and portable V4 application backup.
- Registered `v5.0.0-replicated-cloud` evidence covering three canonical runs,
  experiment and failure-drill, with all 49 scenario executions passing.

### Compatibility

Replication is opt-in and requires a new sealed group. V5.0 does not provide
automatic election, public follower reads, dynamic membership, mixed-version
replication, rolling upgrades or in-place V4 conversion. Existing single-node
applications retain the published V4.4 search and storage semantics.

### Publication verification

Signed tag `v5.0.0` identifies commit
`e6afb5349c018fe163d4938d7637a4de8854d4ea`. The
[release workflow](https://github.com/patricklfdm/GeneralSearchEngine/actions/runs/35428718030)
passed. All twelve published POM/JAR files pass detached-signature and checksum
verification, all nine JARs match the frozen canonical hashes, and clean V1–V5
consumers pass against Maven Central.

- [Migration guide](https://github.com/patricklfdm/GeneralSearchEngine/blob/master/docs/v5x/v5.0/MIGRATION_GUIDE.md)
- [Release verification record](https://github.com/patricklfdm/GeneralSearchEngine/blob/master/docs/v5x/v5.0/RELEASE_CHECKLIST.md)
- [Full changelog](https://github.com/patricklfdm/GeneralSearchEngine/blob/master/CHANGELOG.md)
