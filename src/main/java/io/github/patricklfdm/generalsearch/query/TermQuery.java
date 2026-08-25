package io.github.patricklfdm.generalsearch.query;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Matches documents containing one canonical analyzed term. */
public final class TermQuery<T> implements Query<T> {
    private final TextField<T> textField;
    private final String term;

    public TermQuery(TextField<T> textField, String queryText) {
        this.textField = Objects.requireNonNull(textField, "textField");
        List<String> terms = TextQuerySupport.queryTerms(textField, queryText);
        if (terms.size() != 1) {
            throw new IllegalArgumentException(
                    "term query text must analyze to exactly one distinct token");
        }
        this.term = terms.getFirst();
    }

    public TextField<T> textField() {
        return textField;
    }

    public String term() {
        return term;
    }

    @Override
    public boolean matches(T document) {
        return TextQuerySupport.documentTerms(textField, document).contains(term);
    }
}
