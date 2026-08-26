package io.github.patricklfdm.generalsearch.search;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Immutable normalized input shared by V3 and legacy ranked requests. */
record TextSearchInput<T>(
        TextField<T> textField,
        List<String> frozenTerms,
        Query<T> filter,
        int limit,
        Bm25Config config
) {
    TextSearchInput {
        Objects.requireNonNull(textField, "textField");
        frozenTerms = List.copyOf(frozenTerms);
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
        Objects.requireNonNull(config, "config");
    }

    static <T> TextSearchInput<T> from(SearchRequest<T> request) {
        Objects.requireNonNull(request, "request");
        SearchQueryNode<T> node = request.query().node();
        if (!(node instanceof LeafSearchQueryNode<?> untypedLeaf)
                || untypedLeaf.kind() != SearchLeafKind.TEXT) {
            throw new UnsupportedOperationException(
                    "Phase 3 supports only a direct text query leaf");
        }

        @SuppressWarnings("unchecked")
        LeafSearchQueryNode<T> leaf = (LeafSearchQueryNode<T>) untypedLeaf;
        return new TextSearchInput<>(
                leaf.field(),
                analyzeTerms(leaf.field(), leaf.text()),
                request.filter().orElse(null),
                request.limit(),
                request.bm25()
        );
    }

    static <T> TextSearchInput<T> from(RankedSearchRequest<T> request) {
        Objects.requireNonNull(request, "request");
        TextScoringQuery<T> scoringQuery = request.scoringQuery();
        return new TextSearchInput<>(
                scoringQuery.textField(),
                scoringQuery.terms(),
                request.filter().orElse(null),
                request.limit(),
                request.config()
        );
    }

    private static List<String> analyzeTerms(TextField<?> field, String text) {
        List<AnalyzedToken> tokens = field.analyzer().analyzeWithPositions(text);
        if (tokens == null) {
            throw invalidAnalysis(field, "returned a null token list");
        }

        LinkedHashSet<String> terms = new LinkedHashSet<>();
        int logicalPosition = -1;
        for (int index = 0; index < tokens.size(); index++) {
            AnalyzedToken token = tokens.get(index);
            if (token == null) {
                throw invalidAnalysis(field, "returned a null token at index " + index);
            }
            int increment = token.positionIncrement();
            if (index == 0 && increment < 1) {
                throw invalidAnalysis(
                        field,
                        "returned a non-positive first position increment"
                );
            }
            if (increment < 0) {
                throw invalidAnalysis(
                        field,
                        "returned a negative position increment at index " + index
                );
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
            terms.add(token.term());
        }
        return List.copyOf(terms);
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
