package io.github.patricklfdm.generalsearch.analysis;

import java.util.List;

/**
 * Analyzer capability that maps normalized terms and logical positions back to the
 * exact original Java string.
 *
 * <p>Implementations must be deterministic and thread-safe. Every offset is a
 * zero-based, half-open UTF-16 range into the exact {@code text} argument. The
 * projections returned by {@link #analyze(String)} and
 * {@link #analyzeWithPositions(String)} must preserve encounter order and equal the
 * corresponding projection of {@link #analyzeWithOffsets(String)}.</p>
 */
@FunctionalInterface
public interface OffsetAnalyzer extends Analyzer {
    /**
     * Analyzes text with logical positions and original-source UTF-16 offsets.
     *
     * @param text exact source string; implementations define null handling
     * @return non-null offset-aware tokens in deterministic encounter order
     */
    List<OffsetAnalyzedToken> analyzeWithOffsets(String text);

    /**
     * Projects offset-aware output to the legacy term view.
     *
     * @param text exact source passed unchanged to {@link #analyzeWithOffsets(String)}
     * @return immutable term projection in encounter order
     */
    @Override
    default List<Token> analyze(String text) {
        return analyzeWithOffsets(text).stream()
                .map(token -> new Token(token.term()))
                .toList();
    }

    /**
     * Projects offset-aware output to the published position-aware view.
     *
     * @param text exact source passed unchanged to {@link #analyzeWithOffsets(String)}
     * @return immutable term/position projection in encounter order
     */
    @Override
    default List<AnalyzedToken> analyzeWithPositions(String text) {
        return analyzeWithOffsets(text).stream()
                .map(token -> new AnalyzedToken(
                        token.term(),
                        token.positionIncrement()
                ))
                .toList();
    }
}
