# V3 positional semantics

This is a frozen later-phase contract. Phase 0 implements neither `AnalyzedToken` nor
positional storage.

## Future Analyzer API

The future public addition is:

```java
public record AnalyzedToken(String term, int positionIncrement) {
}
```

```java
@FunctionalInterface
public interface Analyzer {
    List<Token> analyze(String text);

    default List<AnalyzedToken> analyzeWithPositions(String text) {
        return analyze(text).stream()
                .map(token -> new AnalyzedToken(token.term(), 1))
                .toList();
    }
}
```

`AnalyzedToken` rejects a null/empty term and a negative increment with
`IllegalArgumentException`. The default adapter calls the existing `analyze(text)` once,
preserves encounter order and duplicates, and maps every `Token` to increment `1`.
`Analyzer` remains a functional interface.

Analyzer output must be a non-null list of non-null tokens with non-empty terms. The
first increment is at least 1; subsequent increments are at least 0. Planning or index
construction rejects invalid output with `IllegalArgumentException` and never repairs
it silently.

## Positions and length

Logical position starts at `-1` and advances by `positionIncrement`. Increment zero is
reserved for same-position alternatives. Document length remains emitted token count,
not maximum logical position plus one; gaps affect phrase matching but not BM25 length.

Future positional postings pair the existing document bitmap with `docId ->
IntPositions`. `IntPositions` is internal, immutable, sorted, primitive-backed, and
non-negative. Term frequency is its size.

## Exact phrase slots

Query tokens become ordered relative-position slots:

1. Compute logical positions and subtract the first token position, making the first
   slot relative position zero.
2. Group equal positions into one slot with OR alternatives in analyzer order.
3. Deduplicate alternatives within a slot in first-encounter order.
4. Preserve the same term when it appears in different slots.

At slop zero, a document matches if some non-negative base position `p` has at least one
alternative from every slot `r` at document position `p + r`. Position gaps must match
exactly, repeated terms must occur at every required position, and a phrase can begin
anywhere. An initial query gap is validated but normalized away. Zero query tokens match
nothing.
