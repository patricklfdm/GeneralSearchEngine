# GeneralSearchEngine 5.2.0 release notes — draft

These notes describe the implemented V5.2 snapshot. **5.2.0 is not published**;
stable remains 5.1.0. Follow the [release checklist](RELEASE_CHECKLIST.md) before
assigning a final date, tag or available coordinates.

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
claim that the local snapshot JARs equal measured cloud JAR bytes. Final candidate
reproducibility, exact-source full CI, signed publication and remote verification
remain Phase 7B/8 work.
