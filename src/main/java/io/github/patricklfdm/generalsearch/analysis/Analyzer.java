package io.github.patricklfdm.generalsearch.analysis;

import java.util.List;

/** Immutable, deterministic, thread-safe conversion from text to normalized tokens. */
@FunctionalInterface
public interface Analyzer {
    /**
     * Analyzes text in deterministic encounter order. Null and empty input may produce
     * an empty list, and duplicate tokens may be retained.
     */
    List<Token> analyze(String text);

    /**
     * Analyzes text with logical-position increments in deterministic encounter order.
     * The default adapter preserves the legacy terms and assigns increment {@code 1}
     * to each token. Overrides must return a non-null list of non-null tokens. Empty
     * output is valid; otherwise the first increment must be positive and every later
     * increment must be non-negative.
     *
     * @param text original text passed unchanged to {@link #analyze(String)}
     * @return unmodifiable position-aware tokens in legacy encounter order
     * @throws RuntimeException if legacy analysis throws one; the same exception is
     *         propagated unchanged
     */
    default List<AnalyzedToken> analyzeWithPositions(String text) {
        return analyze(text).stream()
                .map(token -> new AnalyzedToken(token.term(), 1))
                .toList();
    }

    /** Returns the canonical simple analyzer shipped with v2. */
    static Analyzer simple() {
        return SimpleAnalyzer.INSTANCE;
    }
}
