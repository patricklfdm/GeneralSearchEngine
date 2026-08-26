package io.github.patricklfdm.generalsearch.ranking;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Canonical analyzed terms that contribute BM25 relevance score. */
public final class TextScoringQuery<T> {
    private final TextField<T> textField;
    private final String queryText;
    private final List<String> terms;

    public TextScoringQuery(TextField<T> textField, String queryText) {
        this.textField = Objects.requireNonNull(textField, "textField");
        this.queryText = Objects.requireNonNull(queryText, "queryText");
        LinkedHashSet<String> analyzed = new LinkedHashSet<>();
        for (AnalyzedToken token : positionedTokens(textField, queryText)) {
            analyzed.add(token.term());
        }
        this.terms = List.copyOf(analyzed);
    }

    /** Creates a scoring query over one canonical text field. */
    public static <T> TextScoringQuery<T> of(
            TextField<T> textField,
            String queryText
    ) {
        return new TextScoringQuery<>(textField, queryText);
    }

    public TextField<T> textField() {
        return textField;
    }

    public String queryText() {
        return queryText;
    }

    /** Returns distinct normalized terms in first-encounter order. */
    public List<String> terms() {
        return terms;
    }

    private static List<AnalyzedToken> positionedTokens(
            TextField<?> field,
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
