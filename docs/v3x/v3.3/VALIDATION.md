# V3.3 validation contract

## Independent oracles

V3.3 requires representation-free oracles that do not call production cursor,
continuation, page-retention, or total-count helpers:

- exhaustive oracle evaluates query/filter truth and scores every active document,
  then sorts by score descending and an independent fixture insertion-order ID;
- page oracle slices that exhaustive order by an explicit anchor tuple and page size;
- count oracle counts full-query/filter matches before anchor and limit;
- snapshot oracle records controlled version/publication transitions; and
- retention oracle inspects reachable cursor state without relying on cursor accessors.

Production `SearchExecutor`, its comparators, page helper, or cursor implementation
cannot serve as its own oracle. Randomized failures print seed, corpus, request shape,
page size, anchor, expected order/count, observed order/count, and publication history.

## Public API fixtures

Reflection and source fixtures freeze:

- `SearchAfterCursor` as a zero-method public interface;
- `TotalHitsMode` with exactly `DISABLED` and `EXACT`;
- final page request/result classes and the final nested request builder;
- exact factory, accessor, generic, optional, and exception descriptors;
- the additive default `SearchEngine.search(SearchPageRequest)` method;
- unchanged `SearchRequest`, `SearchResult`, `SearchHit`, highlighted, Explain, query,
  analyzer, schema, mutation, metrics, and processor surfaces; and
- absence of public cursor implementation, snapshot version, score anchor, document
  ID, plan, posting, bitmap, or snapshot types.

Japicmp runs against all six published artifacts in normal clean-home and
fresh-isolated repositories. V1/V2 consumers remain source-unchanged. The V3 consumer
adds only supported page construction, first-page parity, continuation, and exact
total assertions.

## Request/result construction matrix

Builder and factory fixtures cover:

| Shape | Required observation |
|---|---|
| null wrapped request | builder fails immediately |
| default builder | no cursor; total mode `DISABLED` |
| null cursor/mode setter | deterministic null failure |
| builder reuse | earlier built request remains immutable |
| null hit list/element | result factory fails |
| factory without cursor | next-cursor accessor is empty |
| null cursor in cursor overload | factory fails |
| foreign cursor in result | construction succeeds for third-party use |
| negative exact total | exact factory fails |
| disabled total | `OptionalLong.empty()` |
| exact zero/positive total | present exact value |

Request/result values are immutable under mutation of source collections or builder
reuse. No result accepts a sentinel count.

## First-page parity matrix

For controlled snapshots, ordinary and first-page execution compare:

- no hit, fewer than limit, exactly limit, and more than limit;
- TEXT, exact/sloppy PHRASE, FUZZY, nested BOOL, BOOST, and zero-term leaves;
- no filter and indexed/unindexed/custom structured filters;
- default and non-default BM25;
- limits `1`, `2`, `10`, and larger than match count;
- zero scores, dense equal scores, and distinct scores; and
- missing index, malformed analyzer output, and extractor failure.

On an open engine, with total hits disabled, documents, references, raw score bits,
order, cardinality, and query/execution failures equal ordinary search. Exact mode
changes only total presence/value. Closed-engine admission is validated separately
because the new page operation freezes an explicit admitted-read lifecycle contract.

## Cursor validation and failure precedence

Focused fixtures cover:

- application-made/third-party cursor -> `UNSUPPORTED_CURSOR`;
- built-in cursor from another engine -> `DIFFERENT_ENGINE`;
- cursor used with an equivalent-looking new request -> `DIFFERENT_REQUEST`;
- cursor used with the exact request after publication -> `STALE_SNAPSHOT`;
- cursor reused repeatedly without publication -> identical page;
- cursor with changed wrapper total mode -> accepted; and
- cursor passed after engine close -> `CLOSED` before cursor validation.

Combined-invalid fixtures prove the frozen cursor reason order. Cursor validation wins
over later missing-index, analyzer, and filter execution failures after lifecycle
admission.

## Exhaustive pagination matrix

Small-corpus exhaustive tests vary score/order shapes and every page size from one
through match count plus one. Concatenated pages must equal the complete independent
order exactly, with no duplicate or omission.

Focused cases include:

- every hit has the same score;
- first/last anchors inside a large equal-score run;
- repeated document values under different business/internal identities;
- result size exactly divisible and not divisible by page size;
- final page smaller than limit;
- zero/fewer/exactly/more-than-limit matches;
- cursor reuse and branching from the same page; and
- zero-score matching children and filters.

Every emitted cursor corresponds to the page's last hit and exists only when a later
match exists. Empty and final pages expose no cursor.

## Total-hits matrix

Exact totals are compared with the exhaustive match oracle across:

- each ranked leaf and nested composition;
- indexed/unindexed/custom filters;
- cursor at first, middle, penultimate, and final page;
- match count around page limits;
- add/update/remove/bulk histories before the first page;
- dynamic index configurations producing the same truth; and
- `long` result construction boundaries independent of the current int document space.

Every accepted page in one unchanged cursor chain reports the same exact total. The
value counts full matches, not returned or remaining hits. Disabled mode is always
absent and does not execute a separate count path.

## Mutation, dynamic-index, and lifecycle matrix

Deterministic fixtures pause at cursor creation, before second-page snapshot capture,
and after second-page capture. They publish add, update, remove, bulk operations,
dynamic index create, or dynamic index drop.

- publication before capture makes the cursor stale;
- publication after capture lets the admitted page finish entirely from the captured
  snapshot;
- failed/non-publishing work leaves the cursor valid;
- no page contains a mixture of snapshot states; and
- writer completion/progress is independent of retained cursors.

Close-before-call rejects. Close after admitted capture cannot produce partial output.
Cursor/result retention after engine close exposes no usable continuation guarantee.

## Randomized differential requirements

Generators vary corpus, insertion/mutation history, Unicode text, query tree, phrase
slop, fuzzy spelling, BOOL threshold, boosts, filter shape, BM25 values, page size,
total mode, cursor depth, cursor reuse, and publication timing.

Normal CI uses fixed replayable seeds. Bounded exhaustive small-corpus tests enumerate
all equal-score/tie arrangements. Concurrency tests use barriers for state assertions;
they do not infer correctness from timing sleeps.

## Retention and unsupported-state checks

Cursor reachability inspection proves the built-in cursor retains only its small owner
token, exact immutable request reference, snapshot version, score bits, and anchor ID.
It retains no engine, snapshot, document, index registry, posting, bitmap, plan, result,
analyzer output, or executor scratch collection.

The engine retains no cursor registry, TTL queue, cleanup thread, or per-cursor state.
Creating and discarding many cursors must not increase engine-retained state.

## Consumers, artifacts, and documentation

The V3 consumer and travel example execute at least two pages and exact totals using
only supported types. Strict Javadocs document opacity, request identity, stale rules,
total meaning, optionals, lifecycle, and exceptions.

Release packaging, service-entry inspection, reproducibility, API fixtures, and remote
published-consumer gates remain mandatory. Examples must never imply cursor
serialization, mutation-stable pagination, page numbers, lower-bound counts, or
highlighted pagination.
