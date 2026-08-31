# V3.4 API compatibility contract

## Published baselines

V3.4 must remain compatible with published `1.0.0`, `2.0.0`, `2.1.0`, `3.0.0`,
`3.1.0`, `3.2.0`, and `3.3.0`. Normal and fresh-isolated Japicmp runs compare the
candidate core JAR with all seven artifacts. Pinned V3 identities fail closed:

```text
3.0.0 core SHA-256
3b0ed72877f3c5f2ef225d1a87cac8d9546b109c91c0bec8d8dcea12e2d101f2

3.1.0 core SHA-256
d77309b58ceca6b6515177a1edbed20f88d59ec5e3ec9330173e282d53d6c86c

3.2.0 core SHA-256
8cf029b43bdd57ce93c06d71e007f1404c2d1c02c4d4dc6779461dabcd051c1c

3.3.0 core SHA-256
18fb6439be074b39e5f22e2b01fba327ee919a4997e6429551481ef7fb8754f4
```

No baseline may resolve from an unverified local same-coordinate install. Published
POMs, JAR hashes, repository origin, and the isolated Maven repository remain part of
the compatibility gate.

## Zero-addition public API rule

V3.4 authorizes no supported public type, method, constructor, field, enum constant,
record component, implemented interface, annotation, service, or module change.

In particular, V3.4 adds nothing to:

- `Query`, fields, schemas, indexes, analyzers, analyzed tokens, or annotations;
- `SearchQuery`, `SearchQueries`, `SearchRequest`, `SearchResult`, or `SearchHit`;
- highlighted request/result, source fragment/span, or offset APIs;
- page request/result, cursor, total-hits, or cursor exception APIs;
- Explain values, ranking configuration, engine metrics, or lifecycle exceptions;
- `SearchEngine`, its builders, concrete engine constructors, mutation methods, or
  dynamic-index methods; and
- the annotation processor, generated schema/field output, or processor service entry.

Benchmark, probe, fixture, and Cloud Benchmark types remain outside the published core
and processor artifacts. A benchmark convenience API must not leak into `src/main`.

## Behavior compatibility

Zero descriptor change is necessary but not sufficient. V3.4 preserves:

- ordinary structured query results and iteration order;
- V2 BM25 top-K truth, score bits, tie order, and filters;
- V3 TEXT/PHRASE/FUZZY/BOOL/BOOST normalization, matching, scoring, and Explain;
- V3.1 slop and `minimumShouldMatch` defaults and explicit behavior;
- V3.2 offset validation and structured-highlight hit/span/fragment behavior;
- V3.3 first-page parity, continuation order, exact totals, cursor failures, and stale
  policy;
- mutation admission, future completion, batching, failure atomicity, and visibility;
- dynamic-index build/replay/publication/drop behavior; and
- close admission and admitted-read completion.

Hardening workloads do not establish new ordering, timing, queue-capacity, memory,
thread-count, or performance promises for applications.

## Phase conversion

Phase 0 leaves all active core, processor, reactor, example, and compatibility
coordinates at published `3.3.0`. Phase 1 converts all seven active coordinates
atomically to `3.4.0-SNAPSHOT` only after the Phase 0 protected merge and exact-commit
CI pass. Final conversion to `3.4.0` occurs only after Phases 1–4 are accepted.

Historical baseline coordinates, hashes, fixtures, release records, and cloud family
identities never change during conversion.

## Required fixtures and consumers

Phase 1 adds a V3.4 zero-addition contract fixture that compares the complete expected
supported surface with V3.3 and fails on an unreviewed addition or removal. Existing
V1, V2, V3.2, and V3.3 reflection/source fixtures remain active.

Independent consumers remain mandatory:

- V1 and V2 consumers remain source-unchanged;
- the V3 consumer retains ranked, phrase/slop, fuzzy, BOOL, Explain, highlighting, and
  two-page exact-total scenarios without adopting a V3.4 API; and
- the travel example remains a supported-API execution rather than a benchmark hook.

The processor consumer and generated-source checks prove that hardening changes no
annotation-processing descriptor, service entry, or generated shape.

## Production blocker amendment

If evidence finds a production blocker, the amendment must name the exact internal
change and prove that no supported descriptor or behavior above changes. Any proposed
public addition is automatically outside V3.4 and requires a later version contract;
it cannot be smuggled in as a hardening fix.

## Post-publication baseline

After remote publication, the Maven Central `3.4.0` core SHA-256 becomes the eighth
mandatory future baseline only when it matches the recorded reproducible final JAR.
Until that evidence exists, no document may invent or reserve a 3.4 hash.

