# GeneralSearchEngine v1 boundary semantics

This document freezes the observable behavior of the v1 API. It describes the current
contract, not planned capabilities. In particular, v1 does not provide configurable
null policies, custom range comparators, or automatic string normalization.

## Documents and identity

- Documents and business IDs must be non-null.
- Passing a null document to `add` or `update`, or a null ID to `get` or `remove`, is
  rejected synchronously with `NullPointerException`.
- A document whose ID extractor returns null is accepted into the asynchronous queue,
  then its future completes exceptionally with `NullPointerException`; no mutation is
  published.
- A business ID is immutable. `update(replacement)` locates the active document by the
  replacement's ID and cannot rename an existing ID.
- `remove(missingId)` is idempotent. `get(missingId)` returns null.

The engine retains document references; it does not clone, serialize, or defensively
copy objects. `get` and `search` return those same references. Applications must treat
an accepted document as immutable and perform changes with a new replacement object:

```java
engine.update(new Item(existing.id(), "new value")).join();
```

Mutating an accepted object directly is unsupported. It can make stored field values
differ from already-published indexes because the writer did not observe an update.
The caller is also responsible for safely publishing and reading any mutable state
inside a document.

## Null field values

Non-ID extractors may return null unless the application's domain type rejects it.
All built-in indexes use the same fixed v1 policy:

- Equality, Range, and Prefix indexes omit null field values.
- `Query.eq(field, null)` is valid and matches null values with `Objects.equals`.
  Because nulls are not indexed, planning falls back to a safe scan.
- Range and Prefix queries never match a null field value.
- An empty prefix matches every non-null string.
- Updates between null and non-null values remove/add the appropriate index entry.

There is deliberately no `NullPolicy` configuration in v1. Introducing indexed nulls
or rejecting nullable fields would be a future additive feature with explicit schema
configuration.

## Equality and ordering

Equality uses `Objects.equals(actual, expected)`. Therefore equality follows the value
type's `equals` implementation; it is not based on string conversion or ordering.

Range fields must implement `Comparable` for their own type. Ranges are inclusive on
both ends and use `compareTo` in both full scans and Range indexes. A lower bound that
orders after its upper bound produces no matches. Custom comparators are not supported
in v1.

Some types, notably `BigDecimal`, can return zero from `compareTo` while returning
false from `equals`. A Range index groups such values into one ordering bucket and
therefore reports equality candidates as a superset; final `Query.matches` evaluation
preserves `Objects.equals` semantics. Register a separate Equality index on the same
field when exact equality candidate planning is important.

`Float` and `Double` consequently use Java's wrapper ordering and equality semantics:

- negative infinity, finite values, positive infinity, then NaN in natural order;
- a `[negativeInfinity, positiveInfinity]` range excludes NaN;
- `[NaN, NaN]` matches NaN;
- negative zero and positive zero are distinct equality keys.

NaN and infinities are not rejected by the engine. Domain types may impose stricter
validation before documents are submitted.

## Strings, Unicode, locale, and time

String equality and prefix matching are case-sensitive. Prefix queries use
`String.startsWith`, and Prefix index ordering uses Java `String` natural ordering over
the original UTF-16 code units. The engine performs no case folding, trimming, Locale
conversion, collation, or Unicode normalization. Precomposed and decomposed text can
therefore remain distinct.

Applications needing normalized search must expose a consistently normalized field
and normalize query values with the same application-owned function. Normalization
must not depend on mutable process defaults such as the default Locale.

Temporal values are treated like any other equality or `Comparable` value. The engine
does not convert time zones or calendars. Applications should choose a canonical type
and zone (for example `Instant`) before indexing.

## Query composition and result order

- An empty AND matches every active document; an empty OR matches none.
- NOT is evaluated against active documents only.
- Candidate indexes are an optimization. Every candidate is checked with
  `Query.matches`, so indexed and scanned execution must have the same result set.
- Results follow ascending internal document ID (insertion) order. Updating a document
  keeps its position; removing and re-adding the same business ID allocates a new
  internal ID and therefore a new position.

Result ordering is deterministic for one mutation history, but v1 exposes no sorting
API and applications should not treat insertion order as relevance ordering.
