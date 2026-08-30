# V3.1 API compatibility contract

## Baseline

V3.1 is additive to published `1.0.0`, `2.0.0`, `2.1.0`, and `3.0.0`. During V3.1
development, the isolated artifact compatibility profile compared the candidate core
JAR directly with all four published artifacts. Following publication, `3.1.0` is also
a mandatory baseline for every subsequent V3.x candidate. The frozen V1 fixture and
independent V1-, V2-, and V3-style consumer builds remain mandatory.

The `artifact-compat` profile copies the published `3.0.0` and `3.1.0` artifacts into
isolated compatibility-baseline paths and verifies their pinned SHA-256 values before
running Japicmp. The 3.0 pin was essential while that candidate retained version
`3.0.0`; the 3.1 pin now prevents subsequent local development from silently resolving
a locally installed same-coordinate JAR. Both identities fail closed. Every execution
uses the same public-access, synthetic filtering, and binary/source incompatibility
failure policy as the older published baselines.

## Supported public additions

V3.1 permits exactly these supported ranked-query additions:

```java
public static <T> SearchQuery<T> SearchQueries.phrase(
        TextField<T> field,
        String text,
        int slop
)

public SearchQueries.BoolBuilder<T> minimumShouldMatch(int value)
```

The exact generic descriptors, validation, defaults, and behavior are frozen in
[ranked-search semantics](RANKED_SEARCH_SEMANTICS.md). The existing two-argument phrase
factory, BOOL builder methods, `SearchQuery`, `SearchRequest`, `SearchResult`,
`SearchEngine`, ranking types, schema types, and analyzer types remain supported and
unchanged.

No public options object, query-node subtype, slop result type, fuzzy configuration,
cursor, total-hits field, timeout, offset token, highlight type, or vocabulary type is
part of V3.1.

## Existing behavior

- `SearchQueries.phrase(field, text)` remains exact slop zero.
- A BOOL without `minimumShouldMatch(...)` retains V3.0 matching, score, ordering,
  validation, and Explain behavior.
- `SearchQueries.fuzzy(field, text)` retains complete V3.0 expansion and scoring.
- `SearchEngine.search(Query)`, `searchTopK`, mutation completion, snapshot visibility,
  dynamic-index lifecycle, metrics, and close behavior remain unchanged.
- `Analyzer` remains a SAM; `AnalyzedToken` retains its two record components and all
  existing constructors/accessors.

## Unsupported internal additions

Japicmp may report narrow additive methods on the existing Javadoc-hidden
`PhrasePositionAccess` and `FuzzyVocabularyAccess` bridges. They may perform only the
operations authorized by the V3.1 architecture contract. They do not become supported
SPIs and may not expose positions, trie nodes, postings, candidates, snapshots, plans,
or internal document IDs.

Package-private query-node fields, normalized nodes, plans, verification workspaces,
trie nodes, builders, and traversal state carry no compatibility guarantee. No new
bytecode-public bridge class is permitted unless this contract is amended and its
necessity is reviewed before implementation.

## Processor and generated consumers

V3.1 requires no annotation-processor API or generated-source change. The processor,
generated fields, generated schemas, and travel example must continue to compile and
run through the reactor. The independent V3 consumer exercises phrase slop from Phase
2 and `minimumShouldMatch` from Phase 3.

## Version and release evidence

Development version changes, release conversion, signed artifacts, strict Javadocs,
artifact inspection, reproducible builds, and remote published verification follow the
existing protected release process. No compatibility exception may be justified only
because a new method is source-additive; overload resolution, null literals, erasure,
record components, default-interface behavior, and independent compilation must also
be reviewed.

## Phase 8 snapshot and final review

The fresh isolated `3.1.0-SNAPSHOT` comparison resolves the published 3.0.0 core JAR
with SHA-256:

```text
3b0ed72877f3c5f2ef225d1a87cac8d9546b109c91c0bec8d8dcea12e2d101f2
```

The same normal clean-home and fresh-isolated comparisons pass after final `3.1.0`
conversion. Japicmp passes against all four published baselines. The
3.0.0-to-candidate report contains exactly four additive public method descriptors:

- supported `SearchQueries.phrase(TextField<T>, String, int)`;
- supported `SearchQueries.BoolBuilder<T>.minimumShouldMatch(int)`;
- unsupported bridge `PhrasePositionAccess.minimumConsumedSlop(...)`;
- unsupported bridge `FuzzyVocabularyAccess.forEachWithinEditDistance(...)`.

`TextIndexSnapshot` is reported as a modified class with no public method or field
change. No public class, constructor, record component, interface default, or existing
method is added, removed, or incompatibly modified beyond the four reviewed additive
descriptors. The generated report is disposable under `target/japicmp/`; this document
is the reviewed compatibility record.

## Post-publication baseline

The published 3.1.0 core JAR resolves from Maven Central with SHA-256:

```text
d77309b58ceca6b6515177a1edbed20f88d59ec5e3ec9330173e282d53d6c86c
```

That value matches the reproducible final main-JAR hash recorded before tagging. The
post-publication profile compares the current tree with all five published baselines:
`1.0.0`, `2.0.0`, `2.1.0`, pinned `3.0.0`, and pinned `3.1.0`. Later V3.x work may add
new published baselines but must not remove any of these checks.
