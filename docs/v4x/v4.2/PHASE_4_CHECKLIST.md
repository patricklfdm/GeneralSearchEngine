# GeneralSearchEngine V4.2 Phase 4 checklist

- **Status:** Accepted on protected `master`
- **Scope:** Versioned typed transforms and exact target-index rebuild

## Entry

- [x] Phase 3 merged through protected PR #109 as
  `43bf2bda3f51ac28aa4aaa1be8bbd96d63bd6daf`.
- [x] Exact-master CI run `33842969788` passed.
- [x] Work is isolated on `feat/v4.2-phase4-transform-migration`.

## Migration edges and transforms

- [x] `(1,0)` to `(1,1)` admits identity-format or declared typed transformation.
- [x] `(1,1)` to `(1,1)` requires at least one declared identity or index change.
- [x] Exact same-format/same-identity no-op, downgrade, `(1,0)` target, unknown
  format, and hidden multi-hop edges fail closed.
- [x] Source storage, schema, codec, codec version, bounds, profile, and index
  descriptors must exactly match authoritative metadata.
- [x] Every source record produces exactly one target record in the same slot order.
- [x] Target schema key extraction equals the transformed key.
- [x] Target key/document bytes round-trip canonically under the target codec.
- [x] Exact encoded target-key equality detects collisions without hash ambiguity.

## Target indexes and binding

- [x] Target indexes are exactly the definitions owned by the target builder.
- [x] Added, removed, and retained descriptor lists are canonical and exact.
- [x] Planning constructs all target indexes before creating filesystem output.
- [x] Apply rebuilds indexes from transformed canonical documents.
- [x] Descriptor digest binds format, identities, bounds, profile, and ordered indexes.
- [x] Projection binds the target descriptor, transform, history, logical state, and
  every canonical transformed record.
- [x] Plan digest binds paths, source members, descriptors, projection, capacity,
  safety reserve, request limits, and diagnostics bounds.
- [x] Apply rejects changed request/configuration/plan before invoking the transform.
- [x] Apply repeats the full projection and rejects nondeterministic output.

## Failures and source preservation

- [x] Null/throwing transform, key mismatch, collision, codec disagreement, and index
  extractor failure map to `TRANSFORM_FAILURE`.
- [x] Plan/apply projection disagreement maps to `TRANSFORM_NONDETERMINISTIC`.
- [x] Request or plan binding disagreement maps to `PLAN_STALE`.
- [x] Unsupported edges and source identity mismatches retain their frozen reasons.
- [x] Public messages remain stable and exclude application payload data.
- [x] Every tested prepublication failure leaves the final target absent.
- [x] Source member hashes remain byte-identical across successful and failed work.

## Independent and crash evidence

- [x] Independent oracle covers true codec/schema/key/index transformation.
- [x] Independent oracle covers meaningful same-format index migration.
- [x] Separate-JVM catalog harness uses different source and target Java types/codecs.
- [x] Pre-final-rename halt proves target absence and byte-identical source.
- [x] Post-parent-force halt proves typed/searchable target and byte-identical source.
- [x] Evidence remains checksummed and uses the Phase 1-frozen schema.

## Local acceptance

- [x] Focused Phase 4 production, API, oracle, crash and inherited gates pass.
- [x] Full reactor passes with 496 core tests and 5 processor tests; one declared
  core test is skipped and no failure or error occurs.
- [x] Published artifact compatibility, Japicmp and all four consumers pass.
- [x] Bounded JMH smoke passes.
- [x] Release profile, six artifacts, Javadocs and byte reproducibility pass.
- [x] Whitespace and shell/Python syntax gates pass.

## Protected acceptance

- [x] Phase 4 pull request #110 passed every required check.
- [x] Phase 4 merged to protected `master` as
  `043b95b735dbc7dc1f319e2bd64fccba3063597a`.
- [x] Exact protected-master CI run `33846632898` passed.

Phase 5 began after protected acceptance. It owns broader lifecycle,
interruption, cleanup, rollback, and cross-version hardening; Phase 4 does not
authorize those behaviors.
