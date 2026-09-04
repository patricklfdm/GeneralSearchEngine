# GeneralSearchEngine V4.2 Phase 5 local baseline

- **Status:** Accepted on protected `master`
- **Source:** `5687a05aa2f495f58d8acc904ab1e663361cf6e3`
- **Scope:** Lifecycle, authority resolution, migration-remnant cleanup and rollback

## Focused gate

```bash
scripts/verify-v42-phase5-lifecycle.sh
```

The gate covers all 25 frozen production publication/lifecycle barriers, validates
checksummed evidence for each, invokes plan-bound cleanup for every recognizable
remnant, reruns the complete Phase 4/3/2 chain, and exercises successful target
continuation and reopen.

## Cross-version gate

The exact published predecessor proof runs with an isolated Maven repository:

```bash
./mvnw -Dmaven.repo.local=/tmp/gse-v42-phase5-published-m2 \
  -Partifact-compat \
  -Dtest=V42PublishedV41RollbackCompatibilityTest test
```

It passed against the pinned Central `general-search-engine:4.1.0` JAR. The child JVM
contained the compiled rollback probe and published JAR only. It reopened the
untouched `(1,0)` source at sequence `3` after the `(1,1)` target accepted an
additional mutation and checkpoint.

## Local observations

- marker-only, partial/complete staging and published-target remnants are exact;
- changed source bytes, unknown staging members and stale cleanup plans refuse before
  deletion;
- postpublication cleanup deletes the marker only and preserves both stores;
- every crash case preserves source bytes;
- every visible published target is structurally valid and typed/searchable; and
- successful migration leaves no operation marker or staging directory.

## Complete local acceptance

The complete local acceptance matrix passed:

- the reactor reported `500` core tests and `5` processor tests with no failures;
- the two published-artifact compatibility tests skipped by the ordinary reactor
  both passed under the isolated `artifact-compat` profile;
- all four independent consumer projects passed;
- the bounded JMH smoke and its inherited release gates passed;
- the release profile built all modules and six expected JARs with valid manifests,
  service isolation, immutable format fixtures and Javadocs; and
- two clean release builds produced byte-identical artifacts.

The reproducible JAR SHA-256 values were:

```text
e490818f7f5776a7cec4a46943633ed1c3cf580bf35d8e70b3e784a3ea437eb6  general-search-engine-4.2.0-SNAPSHOT-javadoc.jar
245562f30d4f5508564a1939480791e48cea93833a63910e39e18a620fdb0c5b  general-search-engine-4.2.0-SNAPSHOT-sources.jar
a76b1e79c80a4d73ead88995c558ae100b9398ed08aa0413bb05dd8a5320a470  general-search-engine-4.2.0-SNAPSHOT.jar
6810c955b83b889955a619b4a2e775390d8aeafafa5ddff1c7c32afdb6ffc3a5  general-search-engine-processor-4.2.0-SNAPSHOT-javadoc.jar
4e14c2b7395a34d49b8814a9cbf480b8c9ed9e1e1be8617076f36953b181d917  general-search-engine-processor-4.2.0-SNAPSHOT-sources.jar
70762a44fb71c87ab48c2d902080faaeee80407420dc971cf08f679ee95eadc5  general-search-engine-processor-4.2.0-SNAPSHOT.jar
```

The final focused gate was rerun after cleanup-authority locking was strengthened;
all 25 production crash barriers, successful lifecycle coverage and the inherited
Phase 4/3/2 chain passed. Protected PR #111 merged as `5687a05aa2f495f58d8acc904ab1e663361cf6e3`;
exact-master CI run `33880571096` passed. Phase 5 is accepted.
