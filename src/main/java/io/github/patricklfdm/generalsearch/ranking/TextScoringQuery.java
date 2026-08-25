package io.github.patricklfdm.generalsearch.ranking;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.Token;
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
        for (Token token : textField.analyzer().analyze(queryText)) {
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
}
