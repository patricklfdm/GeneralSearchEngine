# V3.2 token metadata and offset semantics

This contract is additive to the published V3 position model. `Analyzer` remains a
functional interface and `AnalyzedToken` remains a two-component record.

## Public capability shape

V3.2 freezes the following supported additions under the existing analysis package:

```java
public record OffsetAnalyzedToken(
        String term,
        int positionIncrement,
        int startOffset,
        int endOffset
) {}

@FunctionalInterface
public interface OffsetAnalyzer extends Analyzer {
    List<OffsetAnalyzedToken> analyzeWithOffsets(String text);

    @Override
    default List<Token> analyze(String text);

    @Override
    default List<AnalyzedToken> analyzeWithPositions(String text);
}
```

The two default adapters preserve encounter order and derive only the older view. They
return immutable lists and never expose a mutable offset-token list. Implementations
may override either adapter for performance, but every output must remain equivalent to
the corresponding projection of `analyzeWithOffsets`.

`OffsetAnalyzedToken` validates its context-free invariants at construction: term is
non-null and non-empty, `positionIncrement` is non-negative, `startOffset` is
non-negative, and `endOffset` is strictly greater than `startOffset`. Sequence- and
source-dependent invariants are validated by engine consumers.

## Offset coordinate system

Offsets are zero-based Java `String` UTF-16 indices into the exact original string
passed to `analyzeWithOffsets`. Every token denotes the half-open range:

```text
[startOffset, endOffset)
```

The range must satisfy:

```text
0 <= startOffset < endOffset <= text.length()
text.substring(startOffset, endOffset) is always valid
```

Neither boundary may split a UTF-16 surrogate pair. Offsets are not Unicode code-point
indices, UTF-8 byte offsets, positions in normalized text, or display-cell columns.
Consumers can apply them directly to the original Java string without a translation
table.

The normalized `term` need not equal the source substring. Lowercasing, NFKC
normalization, accent handling, and later contracted token filters may change spelling
or length. The offset range identifies the minimal contiguous source range that
contributed to the emitted term.

## Sequence validation

For non-null source text, the engine validates the complete offset-aware output before
using any token:

- the list and every element are non-null;
- empty output is valid;
- the first position increment is positive;
- later increments are non-negative;
- logical-position addition cannot overflow;
- every range is within the source and has valid surrogate boundaries;
- a token at a later logical position starts at or after the previous position's end;
- all same-position alternatives use exactly the same start and end offsets; and
- term/position encounter order equals the ordinary positioned-analysis projection.

The last rule is structural, not a requirement to invoke an analyzer twice in
production. Built-in equivalence is tested exhaustively; custom implementations are
responsible for the declared deterministic contract. An invalid sequence fails the
whole operation with an `IllegalArgumentException` naming the text field and token
index where applicable.

Null and empty source field values produce no offset tokens for the built-in analyzer.
The built-in engine does not create a highlight entry for a null/empty field. Query
factory null validation remains unchanged and occurs before offset analysis.

## Positions, alternatives, stop words, and gaps

Logical positions retain their published meaning. Character offsets do not replace
`positionIncrement`:

- a positive increment starts a later logical position;
- zero represents a same-position alternative;
- omitted stop words are represented by a larger later increment and a corresponding
  source gap;
- punctuation and whitespace may create a character gap without creating an extra
  logical position;
- repeated terms remain separate occurrences; and
- the first logical position may contain an initial positive gap that normalization
  later removes exactly as in V3.1.

The first synonym scope, if separately accepted, is a single source token emitting
same-position alternatives with identical offsets. Multi-token expansion, position
length, overlapping later positions, token graphs, and `NYC -> New York`-style graph
semantics are outside this contract.

## Built-in SimpleAnalyzer

`SimpleAnalyzer` becomes offset-capable without changing its existing ordinary output.
For every string, including supplementary code points, combining sequences, and NFKC
expansions:

```text
SimpleAnalyzer.analyze(text)
    == terms(SimpleAnalyzer.analyzeWithOffsets(text))

SimpleAnalyzer.analyzeWithPositions(text)
    == termAndPositionProjection(SimpleAnalyzer.analyzeWithOffsets(text))
```

The offset implementation maps each normalized token back to the minimal contributing
range in the original string. It cannot report indices in an intermediate normalized
buffer. Focused fixtures include composed/decomposed forms, compatibility characters
whose normalized length changes, supplementary letters/digits, punctuation, whitespace,
empty input, and malformed unpaired surrogates. The built-in analyzer treats an
unpaired surrogate as a delimiter; an emitted boundary never splits a valid surrogate
pair.

Ordinary `analyze` and `analyzeWithPositions` retain their direct non-offset path so
existing indexing and search do not pay the offset mapping allocation cost.

## Legacy analyzer behavior

Every published Analyzer lambda and implementation remains valid for indexing,
structured text queries, V2 top-K, V3 search, phrase/fuzzy behavior, and Explain. The
engine never fabricates offsets by searching normalized terms inside source text; that
would be ambiguous after normalization, duplicates, stop words, or synonyms.

When highlighted search requests a canonical field whose configured analyzer does not
implement `OffsetAnalyzer`, the built-in engine fails deterministically with
`UnsupportedOperationException` naming that field. An unsupported requested field does
not silently produce empty fragments, and the engine does not fall back to approximate
substring matching.

A highlighted query may still contain legacy-analyzer fields that were not requested
for highlighting. They participate in match and score normally and simply produce no
field output.

## Immutability and concurrency

Offset token records and all engine-copied output lists are immutable. An analyzer may
be invoked concurrently by writers, ordinary readers, and highlighted readers and must
remain deterministic and thread-safe. The engine retains neither an analyzer-returned
list nor a token object beyond the invocation that consumes it.
