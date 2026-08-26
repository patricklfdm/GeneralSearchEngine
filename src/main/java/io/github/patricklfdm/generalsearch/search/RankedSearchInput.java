package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;

/** Immutable normalized ranked input bound to exactly one search snapshot. */
record RankedSearchInput<T>(
        SearchSnapshot<T> snapshot,
        NormalizedScoringNode<T> root,
        Query<T> filter,
        int limit,
        Bm25Config config,
        boolean hasNonEmptyText
) {
    RankedSearchInput {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(root, "root");
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
        Objects.requireNonNull(config, "config");
    }

    static <T> RankedSearchInput<T> from(
            SearchSnapshot<T> snapshot,
            SearchRequest<T> request
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        SearchQueryNode<T> publicRoot = request.query().node();
        validateSupportedTree(publicRoot);
        NormalizedScoringNode<T> root = normalize(snapshot, publicRoot);
        return new RankedSearchInput<>(
                snapshot,
                root,
                request.filter().orElse(null),
                request.limit(),
                request.bm25(),
                containsNonEmptyText(root)
        );
    }

    static <T> RankedSearchInput<T> from(
            SearchSnapshot<T> snapshot,
            RankedSearchRequest<T> request
    ) {
        Objects.requireNonNull(snapshot, "snapshot");
        Objects.requireNonNull(request, "request");
        TextScoringQuery<T> scoringQuery = request.scoringQuery();
        List<String> frozenTerms = scoringQuery.terms();
        NormalizedTextNode<T> root = normalizedText(
                snapshot,
                scoringQuery.textField(),
                frozenTerms
        );
        return new RankedSearchInput<>(
                snapshot,
                root,
                request.filter().orElse(null),
                request.limit(),
                request.config(),
                !frozenTerms.isEmpty()
        );
    }

    private static <T> void validateSupportedTree(SearchQueryNode<T> node) {
        if (node instanceof LeafSearchQueryNode<?> untypedLeaf) {
            if (untypedLeaf.kind() != SearchLeafKind.TEXT) {
                throw new UnsupportedOperationException(
                        "Phase 4 supports TEXT, BOOL, and BOOST; "
                                + untypedLeaf.kind() + " execution is not implemented"
                );
            }
            return;
        }
        if (node instanceof BoolSearchQueryNode<?> untypedBool) {
            @SuppressWarnings("unchecked")
            BoolSearchQueryNode<T> bool = (BoolSearchQueryNode<T>) untypedBool;
            for (SearchQuery<T> child : bool.must()) {
                validateSupportedTree(child.node());
            }
            for (SearchQuery<T> child : bool.should()) {
                validateSupportedTree(child.node());
            }
            return;
        }
        if (node instanceof BoostSearchQueryNode<?> untypedBoost) {
            @SuppressWarnings("unchecked")
            BoostSearchQueryNode<T> boost = (BoostSearchQueryNode<T>) untypedBoost;
            validateSupportedTree(boost.query().node());
            return;
        }
        throw new UnsupportedOperationException(
                "unsupported ranked query node: " + node.getClass().getName());
    }

    private static <T> NormalizedScoringNode<T> normalize(
            SearchSnapshot<T> snapshot,
            SearchQueryNode<T> node
    ) {
        if (node instanceof LeafSearchQueryNode<?> untypedLeaf) {
            @SuppressWarnings("unchecked")
            LeafSearchQueryNode<T> leaf = (LeafSearchQueryNode<T>) untypedLeaf;
            return normalizedText(
                    snapshot,
                    leaf.field(),
                    analyzeTerms(leaf.field(), leaf.text())
            );
        }
        if (node instanceof BoolSearchQueryNode<?> untypedBool) {
            @SuppressWarnings("unchecked")
            BoolSearchQueryNode<T> bool = (BoolSearchQueryNode<T>) untypedBool;
            List<NormalizedScoringNode<T>> must = new ArrayList<>(bool.must().size());
            for (SearchQuery<T> child : bool.must()) {
                must.add(normalize(snapshot, child.node()));
            }
            List<NormalizedScoringNode<T>> should = new ArrayList<>(bool.should().size());
            for (SearchQuery<T> child : bool.should()) {
                should.add(normalize(snapshot, child.node()));
            }
            return new NormalizedBoolNode<>(must, should);
        }
        if (node instanceof BoostSearchQueryNode<?> untypedBoost) {
            @SuppressWarnings("unchecked")
            BoostSearchQueryNode<T> boost = (BoostSearchQueryNode<T>) untypedBoost;
            return new NormalizedBoostNode<>(
                    normalize(snapshot, boost.query().node()),
                    boost.multiplier()
            );
        }
        throw new IllegalStateException(
                "validated ranked query changed shape: " + node.getClass().getName());
    }

    private static <T> NormalizedTextNode<T> normalizedText(
            SearchSnapshot<T> snapshot,
            TextField<T> field,
            List<String> terms
    ) {
        List<String> frozenTerms = List.copyOf(terms);
        TextIndexSnapshot<T> textIndex = frozenTerms.isEmpty()
                ? null
                : requireTextIndex(snapshot, field);
        return new NormalizedTextNode<>(field, frozenTerms, textIndex);
    }

    private static boolean containsNonEmptyText(NormalizedScoringNode<?> node) {
        if (node instanceof NormalizedTextNode<?> text) {
            return !text.frozenTerms().isEmpty();
        }
        if (node instanceof NormalizedBoolNode<?> bool) {
            for (NormalizedScoringNode<?> child : bool.must()) {
                if (containsNonEmptyText(child)) {
                    return true;
                }
            }
            for (NormalizedScoringNode<?> child : bool.should()) {
                if (containsNonEmptyText(child)) {
                    return true;
                }
            }
            return false;
        }
        return containsNonEmptyText(((NormalizedBoostNode<?>) node).child());
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

    private static <T> TextIndexSnapshot<T> requireTextIndex(
            SearchSnapshot<T> snapshot,
            TextField<T> canonicalTextField
    ) {
        for (IndexSnapshot<T> candidate : snapshot.indexes().indexes()) {
            if (candidate instanceof TextIndexSnapshot<?> text
                    && text.textField() == canonicalTextField) {
                @SuppressWarnings("unchecked")
                TextIndexSnapshot<T> typed = (TextIndexSnapshot<T>) text;
                return typed;
            }
        }
        throw new IllegalStateException(
                "ranked search requires the canonical text index: "
                        + canonicalTextField.name());
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

sealed interface NormalizedScoringNode<T>
        permits NormalizedTextNode, NormalizedBoolNode, NormalizedBoostNode {
}

record NormalizedTextNode<T>(
        TextField<T> textField,
        List<String> frozenTerms,
        TextIndexSnapshot<T> textIndex
) implements NormalizedScoringNode<T> {
    NormalizedTextNode {
        Objects.requireNonNull(textField, "textField");
        frozenTerms = List.copyOf(frozenTerms);
        if (!frozenTerms.isEmpty()) {
            Objects.requireNonNull(textIndex, "textIndex");
        }
    }
}

record NormalizedBoolNode<T>(
        List<NormalizedScoringNode<T>> must,
        List<NormalizedScoringNode<T>> should
) implements NormalizedScoringNode<T> {
    NormalizedBoolNode {
        must = List.copyOf(must);
        should = List.copyOf(should);
    }
}

record NormalizedBoostNode<T>(
        NormalizedScoringNode<T> child,
        double multiplier
) implements NormalizedScoringNode<T> {
    NormalizedBoostNode {
        Objects.requireNonNull(child, "child");
        if (!Double.isFinite(multiplier) || multiplier <= 0.0) {
            throw new IllegalArgumentException("boost must be finite and positive");
        }
    }
}
