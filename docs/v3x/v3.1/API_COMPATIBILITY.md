# V3.1 API compatibility contract

## Baseline

V3.1 is additive to published `1.0.0`, `2.0.0`, `2.1.0`, and `3.0.0`. The isolated
artifact compatibility profile must compare the candidate core JAR directly with all
four published artifacts. The frozen V1 fixture and independent V1-, V2-, and V3-style
consumer builds remain mandatory.

The `artifact-compat` profile copies the published `3.0.0` artifact into an isolated
compatibility-baseline path and verifies its pinned SHA-256 before running Japicmp.
This is required while the candidate retains version `3.0.0`: dependency coordinates
alone could otherwise resolve a locally installed candidate and silently compare the
JAR with itself. A mismatched baseline fails closed. The execution uses the same
public-access, synthetic filtering, and binary/source incompatibility failure policy
as the existing published baselines.

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
