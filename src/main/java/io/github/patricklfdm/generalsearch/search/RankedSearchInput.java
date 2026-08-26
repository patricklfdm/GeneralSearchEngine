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
        boolean hasNonEmptyScoringLeaf
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
                containsNonEmptyScoringLeaf(root)
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
            if (untypedLeaf.kind() == SearchLeafKind.FUZZY) {
                throw new UnsupportedOperationException(
                        "Phase 5 supports TEXT, PHRASE, BOOL, and BOOST; "
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
            PositionedAnalysis analysis = analyze(leaf.field(), leaf.text());
            return switch (leaf.kind()) {
                case TEXT -> normalizedText(
                        snapshot,
                        leaf.field(),
                        analysis.distinctTerms()
                );
                case PHRASE -> normalizedPhrase(
                        snapshot,
                        leaf.field(),
                        analysis
                );
                case FUZZY -> throw new IllegalStateException(
                        "validated ranked query changed leaf kind: FUZZY");
            };
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

    private static <T> NormalizedPhraseNode<T> normalizedPhrase(
            SearchSnapshot<T> snapshot,
            TextField<T> field,
            PositionedAnalysis analysis
    ) {
        List<PhraseSlot> slots = phraseSlots(analysis.occurrences());
        TextIndexSnapshot<T> textIndex = slots.isEmpty()
                ? null
                : requireTextIndex(snapshot, field);
        return new NormalizedPhraseNode<>(
                field,
                slots,
                analysis.distinctTerms(),
                textIndex
        );
    }

    private static boolean containsNonEmptyScoringLeaf(NormalizedScoringNode<?> node) {
        if (node instanceof NormalizedTextNode<?> text) {
            return !text.frozenTerms().isEmpty();
        }
        if (node instanceof NormalizedPhraseNode<?> phrase) {
            return !phrase.slots().isEmpty();
        }
        if (node instanceof NormalizedBoolNode<?> bool) {
            for (NormalizedScoringNode<?> child : bool.must()) {
                if (containsNonEmptyScoringLeaf(child)) {
                    return true;
                }
            }
            for (NormalizedScoringNode<?> child : bool.should()) {
                if (containsNonEmptyScoringLeaf(child)) {
                    return true;
                }
            }
            return false;
        }
        return containsNonEmptyScoringLeaf(((NormalizedBoostNode<?>) node).child());
    }

    private static PositionedAnalysis analyze(TextField<?> field, String text) {
        List<AnalyzedToken> tokens = field.analyzer().analyzeWithPositions(text);
        if (tokens == null) {
            throw invalidAnalysis(field, "returned a null token list");
        }

        List<PositionedTerm> occurrences = new ArrayList<>(tokens.size());
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
            occurrences.add(new PositionedTerm(token.term(), logicalPosition));
            terms.add(token.term());
        }
        return new PositionedAnalysis(
                occurrences,
                List.copyOf(terms)
        );
    }

    private static List<PhraseSlot> phraseSlots(List<PositionedTerm> occurrences) {
        if (occurrences.isEmpty()) {
            return List.of();
        }

        int firstPosition = occurrences.getFirst().logicalPosition();
        List<PhraseSlot> slots = new ArrayList<>();
        int currentRelativePosition = -1;
        LinkedHashSet<String> alternatives = new LinkedHashSet<>();
        for (PositionedTerm occurrence : occurrences) {
            int relativePosition = Math.subtractExact(
                    occurrence.logicalPosition(),
                    firstPosition
            );
            if (relativePosition != currentRelativePosition) {
                if (!alternatives.isEmpty()) {
                    slots.add(new PhraseSlot(
                            currentRelativePosition,
                            List.copyOf(alternatives)
                    ));
                }
                currentRelativePosition = relativePosition;
                alternatives = new LinkedHashSet<>();
            }
            alternatives.add(occurrence.term());
        }
        slots.add(new PhraseSlot(
                currentRelativePosition,
                List.copyOf(alternatives)
        ));
        return List.copyOf(slots);
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
        permits NormalizedTextNode, NormalizedPhraseNode,
        NormalizedBoolNode, NormalizedBoostNode {
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

record PhraseSlot(int relativePosition, List<String> alternatives) {
    PhraseSlot {
        if (relativePosition < 0) {
            throw new IllegalArgumentException(
                    "relativePosition must not be negative");
        }
        alternatives = List.copyOf(alternatives);
        if (alternatives.isEmpty()) {
            throw new IllegalArgumentException(
                    "a phrase slot requires at least one alternative");
        }
    }
}

record NormalizedPhraseNode<T>(
        TextField<T> textField,
        List<PhraseSlot> slots,
        List<String> scoringTerms,
        TextIndexSnapshot<T> textIndex
) implements NormalizedScoringNode<T> {
    NormalizedPhraseNode {
        Objects.requireNonNull(textField, "textField");
        slots = List.copyOf(slots);
        scoringTerms = List.copyOf(scoringTerms);
        int previousPosition = -1;
        for (int index = 0; index < slots.size(); index++) {
            PhraseSlot slot = slots.get(index);
            if (index == 0 && slot.relativePosition() != 0) {
                throw new IllegalArgumentException(
                        "the first phrase slot must have relative position zero");
            }
            if (slot.relativePosition() <= previousPosition) {
                throw new IllegalArgumentException(
                        "phrase slot positions must be strictly increasing");
            }
            previousPosition = slot.relativePosition();
        }
        if (slots.isEmpty()) {
            if (!scoringTerms.isEmpty()) {
                throw new IllegalArgumentException(
                        "an empty phrase cannot carry scoring terms");
            }
        } else {
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

record PositionedTerm(String term, int logicalPosition) {
    PositionedTerm {
        Objects.requireNonNull(term, "term");
        if (logicalPosition < 0) {
            throw new IllegalArgumentException(
                    "logicalPosition must not be negative");
        }
    }
}

record PositionedAnalysis(
        List<PositionedTerm> occurrences,
        List<String> distinctTerms
) {
    PositionedAnalysis {
        occurrences = List.copyOf(occurrences);
        distinctTerms = List.copyOf(distinctTerms);
    }
}
