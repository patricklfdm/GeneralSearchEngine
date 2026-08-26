package io.github.patricklfdm.generalsearch.query;

import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.schema.TextField;

final class TextQuerySupport {
    private TextQuerySupport() {}

    static <T> List<String> queryTerms(TextField<T> field, String queryText) {
        Objects.requireNonNull(queryText, "queryText");
        LinkedHashSet<String> terms = new LinkedHashSet<>();
        for (AnalyzedToken token : positionedTokens(field, queryText)) {
            terms.add(token.term());
        }
        return List.copyOf(terms);
    }

    static <T> Set<String> documentTerms(TextField<T> field, T document) {
        Set<String> terms = new HashSet<>();
        String text = field.field().valueOf(document);
        for (AnalyzedToken token : positionedTokens(field, text)) {
            terms.add(token.term());
        }
        return terms;
    }

    private static <T> List<AnalyzedToken> positionedTokens(
            TextField<T> field,
            String text
    ) {
        List<AnalyzedToken> tokens = field.analyzer().analyzeWithPositions(text);
        if (tokens == null) {
            throw invalidAnalysis(field, "returned a null token list");
        }
        int logicalPosition = -1;
        for (int index = 0; index < tokens.size(); index++) {
            AnalyzedToken token = tokens.get(index);
            if (token == null) {
                throw invalidAnalysis(field, "returned a null token at index " + index);
            }
            if (token.term() == null || token.term().isEmpty()) {
                throw invalidAnalysis(field, "returned an empty term at index " + index);
            }
            int increment = token.positionIncrement();
            if (index == 0 && increment < 1) {
                throw invalidAnalysis(
                        field, "returned a non-positive first position increment");
            }
            if (increment < 0) {
                throw invalidAnalysis(
                        field, "returned a negative position increment at index " + index);
            }
            try {
                logicalPosition = Math.addExact(logicalPosition, increment);
            } catch (ArithmeticException failure) {
                throw invalidAnalysis(
                        field,
                        "overflowed logical position at token index " + index,
                        failure
                );
            }
        }
        return tokens;
    }

    private static IllegalArgumentException invalidAnalysis(
            TextField<?> field,
            String detail
    ) {
        return new IllegalArgumentException(
                "Analyzer for text field '" + field.name() + "' " + detail);
    }

    private static IllegalArgumentException invalidAnalysis(
            TextField<?> field,
            String detail,
            RuntimeException cause
    ) {
        return new IllegalArgumentException(
                "Analyzer for text field '" + field.name() + "' " + detail,
                cause
        );
    }
}
