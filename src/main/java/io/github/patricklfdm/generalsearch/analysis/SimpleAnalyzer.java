package io.github.patricklfdm.generalsearch.analysis;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Locale-independent NFKC/lowercase analyzer using non-letter/digit boundaries.
 */
public enum SimpleAnalyzer implements Analyzer {
    /** Shared stateless analyzer instance. */
    INSTANCE;

    @Override
    public List<Token> analyze(String text) {
        if (text == null || text.isEmpty()) {
            return List.of();
        }
        String normalized = Normalizer.normalize(text, Normalizer.Form.NFKC)
                .toLowerCase(Locale.ROOT);
        List<Token> tokens = new ArrayList<>();
        StringBuilder term = new StringBuilder();
        normalized.codePoints().forEach(codePoint -> {
            if (Character.isLetterOrDigit(codePoint)) {
                term.appendCodePoint(codePoint);
            } else if (!term.isEmpty()) {
                tokens.add(new Token(term.toString()));
                term.setLength(0);
            }
        });
        if (!term.isEmpty()) {
            tokens.add(new Token(term.toString()));
        }
        return List.copyOf(tokens);
    }
}
