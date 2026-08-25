package io.github.patricklfdm.generalsearch.query;

import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Matches documents containing at least one distinct analyzed query term. */
public final class AnyTermsQuery<T> implements Query<T> {
    private final TextField<T> textField;
    private final List<String> terms;

    public AnyTermsQuery(TextField<T> textField, String queryText) {
        this.textField = Objects.requireNonNull(textField, "textField");
        this.terms = TextQuerySupport.queryTerms(textField, queryText);
    }

    public TextField<T> textField() {
        return textField;
    }

    public List<String> terms() {
        return terms;
    }

    @Override
    public boolean matches(T document) {
        if (terms.isEmpty()) {
            return false;
        }
        Set<String> documentTerms = TextQuerySupport.documentTerms(textField, document);
        return terms.stream().anyMatch(documentTerms::contains);
    }
}
