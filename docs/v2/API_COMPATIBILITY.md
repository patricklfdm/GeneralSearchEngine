# GeneralSearchEngine v2 API compatibility

## Status

Version `2.1.0` is binary- and source-compatible with the supported application APIs
published in `1.0.0` and `2.0.0`. The frozen v1 compile/reflection fixture and the dual
artifact-level gate verify these guarantees against the Maven Central JARs.

The compatibility result does not promote every public implementation class to a
supported API. The v1 boundary remains the application surface documented in
[`../v1/API_COMPATIBILITY.md`](../v1/API_COMPATIBILITY.md): engine construction and
operations, schemas and annotations, typed queries, the index extension interfaces and
definition factories, metrics/exceptions, and the Product compatibility facade.
Bitmap, storage, concrete index implementation, internal, benchmark, and test packages
remain unsupported implementation surfaces.

## Artifact-level gate

The `artifact-compat` profile uses `japicmp-maven-plugin` 0.24.2. It resolves the
published `1.0.0` and `2.0.0` core JARs from Maven Central and compares each baseline
with the currently packaged artifact. Both executions write HTML, Markdown, XML, and
text reports under `target/japicmp`; the build fails when either comparison finds a
binary or source incompatibility:

```bash
mvn clean -Partifact-compat verify
```

The reports are separated by baseline:

```text
target/japicmp/compare-published-v1-api.*
target/japicmp/compare-published-v2-api.*
```

The accepted P7 comparison against 1.0.0 reports no incompatible modification. The
2.0.0 baseline additionally protects APIs introduced by the stable v2 release when
preparing 2.1. Existing classes, generic signatures, record descriptors, constructors,
methods, exceptions, and enum constants must remain linkable. Reported changes from
1.0.0 through 2.0.0 are additive or internal:

| Phase | Public change | Classification |
|---|---|---|
| P1 | estimation statistics and optional `EstimatingIndexSnapshot` | additive capability; v1 `IndexSnapshot` unchanged |
| P2 | bitmap/dictionary implementation changes | unsupported implementation surface |
| P3 | `PlannerConfig`, `RangePlanningMode`, builder/configured constructor | additive; query truth unchanged |
| P4 | Analyzer, `TextField`, text queries and text index definition | additive v2 API |
| P5 | BM25 request/configuration/hit types and `searchTopK` | additive default interface capability |
| P6 | `addAll`/`updateAll`/`removeAll`, bulk failure context | additive default interface capability |
| P6 | separate generated-field processor artifact | opt-in compile-time artifact; absent from core service metadata |

The ranked-retrieval and bulk-mutation `SearchEngine` methods are defaults so already
compiled third-party v1 engine implementations still link. They throw
`UnsupportedOperationException` until that implementation explicitly supports the
capability. The built-in snapshot engine overrides them.

## Consumer fixtures

Independent Maven projects compile both a v1-style application and a v2.1-style
application against locally installed `2.1.0` artifacts. The v2.1 fixture also runs the
separate annotation processor and consumes its generated schema and field class:

```bash
bash scripts/verify-consumer-projects.sh
```

To verify the published 2.0.0 release explicitly, run the stable v1-style consumer:

```bash
mvn -f compatibility/v1-style-consumer/pom.xml \
    -Dgse.version=2.0.0 clean test
```

The v2.1 consumer intentionally exercises APIs added after 2.0.0 and therefore must use
the locally installed `2.1.0` artifacts.

Behavioral compatibility remains guarded separately by the v1 semantics and the
randomized/differential suites. Artifact compatibility alone cannot prove query truth,
ordering, publication, or concurrency behavior.

## 2.1 additive configuration behavior

The schema-copy behavior added after the frozen 2.0.0 release changes no existing
public method or descriptor. `SearchEngine.builder(schema)` now supports additive field
and `TextField` registration by creating a new immutable schema only when the
configuration is extended. An unextended builder preserves the supplied schema
instance, including the identity behavior covered by the frozen v1 compatibility
fixture.

Canonical-field validation remains intact. Existing v1-style builders, third-party
`SearchEngine` implementations, query truth, snapshot publication, mutation behavior,
and ranked retrieval are unaffected.

The development line also adds the `@SearchField` annotation and
`SearchEngineBuilder.textIndex(String, Analyzer)` convenience. Both are additive:
existing annotation discovery is unchanged, `@SearchIndex` still implies schema
registration plus a startup index, and advanced explicit `TextField` configuration
remains supported.

`SearchEngine.field(...)` and `SearchEngine.textField(...)` are additive default
methods that delegate to `schema()`. Existing third-party implementations therefore
inherit the convenience API without recompilation or implementation changes, and the
returned objects preserve canonical schema identity.
