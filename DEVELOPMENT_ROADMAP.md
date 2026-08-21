# GeneralSearchEngine development roadmap

## v1.0.0 freeze

Version 1.0.0 is feature-frozen. Its release identity is
`io.github.patricklfdm:general-search-engine:1.0.0`, with public Java packages rooted
at `io.github.patricklfdm.generalsearch`. Release-finalization work is limited to
compatibility, documentation, licensing, metadata, validation, and artifact inspection.

The v1.0.0 feature set consists of typed equality, inclusive range, prefix, AND, OR,
NOT and MatchAll queries; immutable in-memory snapshots; synchronous reads;
asynchronous batched mutations; runtime index lifecycle management; and operational
metrics. The observable contract is frozen in
[`docs/V1_SEMANTICS.md`](docs/V1_SEMANTICS.md), and the supported application API is
recorded in [`docs/V1_API_COMPATIBILITY.md`](docs/V1_API_COMPATIBILITY.md).

## Beyond v1.0.0

The following are explicitly out of scope for v1.0.0 and must not be introduced as
part of release finalization:

- full-text search and BM25 ranking;
- fuzzy search;
- write-ahead logging (WAL) and persistence;
- distributed search and sharding.

Any future work in these areas requires separate design, compatibility, performance,
and release planning after v1.0.0.
