package io.github.patricklfdm.generalsearch.query;

import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.schema.TextField;

final class TextQuerySupport {
    private TextQuerySupport() {}

    static <T> List<String> queryTerms(TextField<T> field, String queryText) {
        Objects.requireNonNull(queryText, "queryText");
        LinkedHashSet<String> terms = new LinkedHashSet<>();
        for (Token token : field.analyzer().analyze(queryText)) {
            terms.add(token.term());
        }
        return List.copyOf(terms);
    }

    static <T> Set<String> documentTerms(TextField<T> field, T document) {
        Set<String> terms = new HashSet<>();
        for (Token token : field.analyzeDocument(document)) {
            terms.add(token.term());
        }
        return terms;
    }
}
