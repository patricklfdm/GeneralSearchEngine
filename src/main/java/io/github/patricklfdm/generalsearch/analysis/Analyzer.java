package io.github.patricklfdm.generalsearch.analysis;

import java.util.List;

/**
 * Deterministic conversion from text to normalized tokens.
 *
 * <p>An analyzer may be called concurrently by search and index operations. Custom
 * implementations used by an engine must therefore be thread-safe.</p>
 */
@FunctionalInterface
public interface Analyzer {
    /**
     * Analyzes text in deterministic encounter order. Null and empty input may produce
     * an empty list, and duplicate tokens may be retained.
     *
     * @param text source text; implementations define null handling
     * @return non-null tokens in deterministic encounter order
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
     * @return non-null position-aware tokens in deterministic encounter order; the
     *         default adapter returns an unmodifiable list
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
