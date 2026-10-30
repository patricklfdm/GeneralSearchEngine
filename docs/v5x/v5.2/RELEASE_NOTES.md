# GeneralSearchEngine 5.2.0 release notes

**5.2.0 is published**, dated October 29, 2026 (America/Los_Angeles).
Signed tag `v5.2.0` points to `0743490458c07ef87423b8cd4d4dcf8565dbac93`.
The [release record](RELEASE_CHECKLIST.md) links exact-source full CI, all three
successful Release jobs, Maven Central publication and independent verification.

## Added

- Explicit asynchronous `read(options, callback)` on automatic replication,
  with leader-strong, stale-allowed and same-history minimum-index policies.
- Verified follower application publication, bounded asynchronous progress waits
  and callback-scoped views over one committed application cut.
- Immutable 112-byte history-bound client tokens and distinct validation,
  history, progress and view-lifetime errors.

## Preserved boundaries

The ordinary read API remains strong and leader-based. The optional replication
artifact adds six public types and one default method; independent implementations
can retain its unsupported-capability behavior. Core/configured-leader behavior,
GSER/GSRP formats and existing cursor semantics are unchanged. Tokens neither
authenticate commits nor retain historical snapshots. There is no new follower
paging, dynamic membership, mixed-version protocol or rolling-upgrade guarantee.
See the [migration guide](MIGRATION_GUIDE.md) for supported deployment and failure
handling, including indeterminate writes.

## Qualification

Protected verify-set `40841038976/1` accepted fifteen original execution units
representing three canonical rounds, five failure-drill shards and experiment:
33 histories, 28 formal histories, 27428 reads, 2760 updates, 2700 nominal M01
seconds and 439 formal negatives per location. The
[registration](PHASE_6_CLOUD_ACCEPTANCE.md) records the original sources/sequences,
byte-compatible quota continuation and single retention-only recovery. Historical
failed attempts remain visible; reserved costs are not a provider bill.

Phase 7A binds those original compact records and unchanged runtime/build sources
to snapshot packaging/API checks. It does not replay cloud histories again or
claim that the local snapshot JARs equal measured cloud JAR bytes. Phase 7B froze
final coordinates and reproducible unsigned bytes. Exact-source full CI passed
all 62 jobs; Release `41010395652/1` published the signed source. Independent
remote verification passed twelve POM/JAR signatures/checksums, twelve canonical
hashes and seven fresh consumers (26 tests). Release receipts are retained for
90 days. Historical cloud failures and the two specific exceptions remain visible.

## Availability

- [Core 5.2.0](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine/5.2.0)
- [Annotation processor 5.2.0](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-processor/5.2.0)
- [Replication 5.2.0](https://central.sonatype.com/artifact/io.github.patricklfdm/general-search-engine-replication/5.2.0)
- [GitHub Release](https://github.com/patricklfdm/GeneralSearchEngine/releases/tag/v5.2.0)
