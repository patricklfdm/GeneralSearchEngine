package io.github.patricklfdm.generalsearch.query;

import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Matches documents containing every distinct analyzed query term. */
public final class AllTermsQuery<T> implements Query<T> {
    private final TextField<T> textField;
    private final List<String> terms;

    public AllTermsQuery(TextField<T> textField, String queryText) {
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
        return documentTerms.containsAll(terms);
    }
}
