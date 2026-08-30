package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;

/** Builds immutable snapshot-bound recursive ranked plans. */
final class SearchPlanner<T> {
    private final CandidatePlanner<T> filterPlanner;
    private final FuzzyTermExpander fuzzyTermExpander;

    SearchPlanner(CandidatePlanner<T> filterPlanner) {
        this(filterPlanner, new TrieFuzzyTermExpander());
    }

    SearchPlanner(
            CandidatePlanner<T> filterPlanner,
            FuzzyTermExpander fuzzyTermExpander
    ) {
        this.filterPlanner = Objects.requireNonNull(filterPlanner, "filterPlanner");
        this.fuzzyTermExpander = Objects.requireNonNull(
                fuzzyTermExpander,
                "fuzzyTermExpander"
        );
    }

    SearchPlan<T> plan(RankedSearchInput<T> input) {
        Objects.requireNonNull(input, "input");
        ScoringPlanNode<T> root = compile(input.root(), input.config());
        if (!input.hasNonEmptyScoringLeaf()) {
            return SearchPlan.empty(input, root);
        }

        ImmutableBitmap candidates = root.candidates();
        if (input.filter() != null) {
            var filterCandidates = filterPlanner.plan(
                    input.snapshot(),
                    input.filter()
            );
            if (filterCandidates.isPresent()) {
                candidates = candidates.and(filterCandidates.get().bitmap());
            }
        }

        return new SearchPlan<>(
                input.snapshot(),
                root,
                candidates,
                input.filter(),
                input.limit()
        );
    }

    private ScoringPlanNode<T> compile(
            NormalizedScoringNode<T> node,
            Bm25Config config
    ) {
        if (node instanceof NormalizedTextNode<?> untypedText) {
            @SuppressWarnings("unchecked")
            NormalizedTextNode<T> text = (NormalizedTextNode<T>) untypedText;
            return compileText(text, config);
        }
        if (node instanceof NormalizedPhraseNode<?> untypedPhrase) {
            @SuppressWarnings("unchecked")
            NormalizedPhraseNode<T> phrase =
                    (NormalizedPhraseNode<T>) untypedPhrase;
            return compilePhrase(phrase, config);
        }
        if (node instanceof NormalizedFuzzyNode<?> untypedFuzzy) {
            @SuppressWarnings("unchecked")
            NormalizedFuzzyNode<T> fuzzy =
                    (NormalizedFuzzyNode<T>) untypedFuzzy;
            return compileFuzzy(fuzzy, config);
        }
        if (node instanceof NormalizedBoolNode<?> untypedBool) {
            @SuppressWarnings("unchecked")
            NormalizedBoolNode<T> bool = (NormalizedBoolNode<T>) untypedBool;
            List<ScoringPlanNode<T>> must = compileChildren(bool.must(), config);
            List<ScoringPlanNode<T>> should = compileChildren(bool.should(), config);
            return new BoolPlan<>(
                    must,
                    should,
                    bool.minimumShouldMatch(),
                    boolCandidates(must, should, bool.minimumShouldMatch())
            );
        }
        @SuppressWarnings("unchecked")
        NormalizedBoostNode<T> boost = (NormalizedBoostNode<T>) node;
        return new BoostPlan<>(compile(boost.child(), config), boost.multiplier());
    }

    private List<ScoringPlanNode<T>> compileChildren(
            List<NormalizedScoringNode<T>> children,
            Bm25Config config
    ) {
        List<ScoringPlanNode<T>> plans = new ArrayList<>(children.size());
        for (NormalizedScoringNode<T> child : children) {
            plans.add(compile(child, config));
        }
        return List.copyOf(plans);
    }

    private TextPlan<T> compileText(
            NormalizedTextNode<T> text,
            Bm25Config config
    ) {
        if (text.frozenTerms().isEmpty()) {
            return new TextPlan<>(
                    text.textField().name(),
                    null,
                    List.of(),
                    List.of(),
                    ImmutableBitmap.empty(),
                    config,
                    0.0
            );
        }

        TextIndexSnapshot<T> textIndex = Objects.requireNonNull(text.textIndex());
        int documentCount = textIndex.statistics().indexedDocumentCount();
        double averageDocumentLength = textIndex.averageDocumentLength();
        List<ScoringTerm> scoringTerms = new ArrayList<>(text.frozenTerms().size());
        ImmutableBitmap firstCandidates = null;
        ImmutableBitmapBuilder candidateUnion = null;
        for (String term : text.frozenTerms()) {
            PostingList posting = textIndex.posting(term);
            int documentFrequency = posting.documentFrequency();
            if (documentFrequency == 0) {
                continue;
            }
            double inverseDocumentFrequency = Bm25Scorer
                    .inverseDocumentFrequency(documentCount, documentFrequency);
            scoringTerms.add(new ScoringTerm(
                    term,
                    posting,
                    inverseDocumentFrequency
            ));
            if (firstCandidates == null) {
                firstCandidates = posting.documents();
            } else {
                if (candidateUnion == null) {
                    candidateUnion = new ImmutableBitmapBuilder(firstCandidates);
                }
                candidateUnion.or(posting.documents());
            }
        }

        ImmutableBitmap candidates = firstCandidates == null
                ? ImmutableBitmap.empty()
                : candidateUnion == null ? firstCandidates : candidateUnion.build();

        return new TextPlan<>(
                text.textField().name(),
                textIndex,
                text.frozenTerms(),
                scoringTerms,
                candidates,
                config,
                averageDocumentLength
        );
    }

    private PhrasePlan<T> compilePhrase(
            NormalizedPhraseNode<T> phrase,
            Bm25Config config
    ) {
        if (phrase.slots().isEmpty()) {
            return PhrasePlan.empty(
                    phrase.textField().name(),
                    config,
                    phrase.slop()
            );
        }

        TextIndexSnapshot<T> textIndex = Objects.requireNonNull(phrase.textIndex());
        int slotCount = phrase.slots().size();
        int[] relativePositions = new int[slotCount];
        PostingList[][] alternativesBySlot = new PostingList[slotCount][];
        List<IndexedCandidates> slotCandidates = new ArrayList<>(slotCount);
        Map<String, PostingList> postingsByTerm = new LinkedHashMap<>();

        int anchorSlot = 0;
        int anchorCardinality = Integer.MAX_VALUE;
        for (int slotIndex = 0; slotIndex < slotCount; slotIndex++) {
            PhraseSlot slot = phrase.slots().get(slotIndex);
            relativePositions[slotIndex] = slot.relativePosition();
            PostingList[] alternatives = new PostingList[slot.alternatives().size()];
            for (int alternativeIndex = 0;
                    alternativeIndex < slot.alternatives().size();
                    alternativeIndex++) {
                String term = slot.alternatives().get(alternativeIndex);
                alternatives[alternativeIndex] = postingsByTerm.computeIfAbsent(
                        term,
                        textIndex::posting
                );
            }
            alternativesBySlot[slotIndex] = alternatives;
            ImmutableBitmap candidates = unionCandidates(alternatives);
            slotCandidates.add(new IndexedCandidates(slotIndex, candidates));
            int cardinality = candidates.cardinality();
            if (cardinality < anchorCardinality) {
                anchorSlot = slotIndex;
                anchorCardinality = cardinality;
            }
        }

        List<IndexedCandidates> physical = new ArrayList<>(slotCandidates);
        physical.sort(Comparator
                .comparingInt((IndexedCandidates slot) ->
                        slot.candidates().cardinality())
                .thenComparingInt(IndexedCandidates::slotIndex));
        ImmutableBitmap candidates = physical.getFirst().candidates();
        for (int index = 1; index < physical.size(); index++) {
            candidates = candidates.and(physical.get(index).candidates());
            if (candidates.isEmpty()) {
                break;
            }
        }

        int documentCount = textIndex.statistics().indexedDocumentCount();
        List<ScoringTerm> scoringTerms = new ArrayList<>(phrase.scoringTerms().size());
        for (String term : phrase.scoringTerms()) {
            PostingList posting = Objects.requireNonNull(postingsByTerm.get(term));
            int documentFrequency = posting.documentFrequency();
            if (documentFrequency == 0) {
                continue;
            }
            scoringTerms.add(new ScoringTerm(
                    term,
                    posting,
                    Bm25Scorer.inverseDocumentFrequency(
                            documentCount,
                            documentFrequency
                    )
            ));
        }

        return new PhrasePlan<>(
                phrase.textField().name(),
                textIndex,
                scoringTerms,
                phrase.scoringTerms(),
                candidates,
                config,
                textIndex.averageDocumentLength(),
                relativePositions,
                alternativesBySlot,
                anchorSlot,
                phrase.slots(),
                phrase.slop()
        );
    }

    private FuzzyPlan<T> compileFuzzy(
            NormalizedFuzzyNode<T> fuzzy,
            Bm25Config config
    ) {
        if (fuzzy.normalizedTerm() == null) {
            return FuzzyPlan.empty(fuzzy.textField().name(), config);
        }

        TextIndexSnapshot<T> textIndex = Objects.requireNonNull(fuzzy.textIndex());
        List<FuzzyExpansion> lexicalExpansions = fuzzyTermExpander.expand(
                textIndex,
                fuzzy.normalizedTerm(),
                BoundedOptimalStringAlignment.autoMaxEdits(fuzzy.normalizedTerm())
        );
        int documentCount = textIndex.statistics().indexedDocumentCount();
        List<FuzzyScoringExpansion> scoringExpansions = new ArrayList<>(
                lexicalExpansions.size()
        );
        ImmutableBitmap firstCandidates = null;
        ImmutableBitmapBuilder candidateUnion = null;
        for (FuzzyExpansion expansion : lexicalExpansions) {
            int documentFrequency = expansion.posting().documentFrequency();
            if (documentFrequency <= 0) {
                throw new IllegalStateException(
                        "fuzzy vocabulary term has an empty posting: "
                                + expansion.term()
                );
            }
            scoringExpansions.add(new FuzzyScoringExpansion(
                    expansion.term(),
                    new ScoringTerm(
                            expansion.term(),
                            expansion.posting(),
                            Bm25Scorer.inverseDocumentFrequency(
                                    documentCount,
                                    documentFrequency
                            )
                    ),
                    expansion.editDistance(),
                    expansion.similarity()
            ));
            if (firstCandidates == null) {
                firstCandidates = expansion.posting().documents();
            } else {
                if (candidateUnion == null) {
                    candidateUnion = new ImmutableBitmapBuilder(firstCandidates);
                }
                candidateUnion.or(expansion.posting().documents());
            }
        }
        ImmutableBitmap candidates = firstCandidates == null
                ? ImmutableBitmap.empty()
                : candidateUnion == null ? firstCandidates : candidateUnion.build();
        return new FuzzyPlan<>(
                fuzzy.textField().name(),
                textIndex,
                fuzzy.normalizedTerm(),
                scoringExpansions,
                candidates,
                config,
                textIndex.averageDocumentLength()
        );
    }

    private ImmutableBitmap unionCandidates(PostingList[] alternatives) {
        ImmutableBitmap first = alternatives[0].documents();
        if (alternatives.length == 1) {
            return first;
        }
        ImmutableBitmapBuilder union = new ImmutableBitmapBuilder(first);
        for (int index = 1; index < alternatives.length; index++) {
            union.or(alternatives[index].documents());
        }
        return union.build();
    }

    private ImmutableBitmap boolCandidates(
            List<ScoringPlanNode<T>> must,
            List<ScoringPlanNode<T>> should,
            int minimumShouldMatch
    ) {
        ImmutableBitmap mustCandidates = intersectCandidates(must);
        if (minimumShouldMatch == 0) {
            return Objects.requireNonNull(mustCandidates);
        }

        ImmutableBitmap shouldCandidates = thresholdCandidates(
                should,
                minimumShouldMatch
        );
        return mustCandidates == null
                ? shouldCandidates
                : mustCandidates.and(shouldCandidates);
    }

    private ImmutableBitmap intersectCandidates(
            List<ScoringPlanNode<T>> children
    ) {
        if (children.isEmpty()) {
            return null;
        }
        List<ScoringPlanNode<T>> physical = new ArrayList<>(children);
        physical.sort(Comparator.comparingInt(
                child -> child.candidates().cardinality()));
        ImmutableBitmap candidates = physical.getFirst().candidates();
        for (int index = 1; index < physical.size(); index++) {
            candidates = candidates.and(physical.get(index).candidates());
            if (candidates.isEmpty()) {
                break;
            }
        }
        return candidates;
    }

    private ImmutableBitmap thresholdCandidates(
            List<ScoringPlanNode<T>> children,
            int minimumShouldMatch
    ) {
        if (minimumShouldMatch == 1) {
            ImmutableBitmap first = children.getFirst().candidates();
            if (children.size() == 1) {
                return first;
            }
            ImmutableBitmapBuilder union = new ImmutableBitmapBuilder(first);
            for (int index = 1; index < children.size(); index++) {
                union.or(children.get(index).candidates());
            }
            return union.build();
        }
        if (minimumShouldMatch == children.size()) {
            return Objects.requireNonNull(intersectCandidates(children));
        }

        Map<Integer, Integer> occurrenceCounts = new LinkedHashMap<>();
        for (ScoringPlanNode<T> child : children) {
            child.candidates().forEachSetBit(docId -> occurrenceCounts.merge(
                    docId,
                    1,
                    Integer::sum
            ));
        }
        ImmutableBitmapBuilder threshold = new ImmutableBitmapBuilder(
                ImmutableBitmap.empty());
        occurrenceCounts.forEach((docId, count) -> {
            if (count >= minimumShouldMatch) {
                threshold.set(docId);
            }
        });
        return threshold.build();
    }
}

record IndexedCandidates(int slotIndex, ImmutableBitmap candidates) {
    IndexedCandidates {
        if (slotIndex < 0) {
            throw new IllegalArgumentException("slotIndex must not be negative");
        }
        Objects.requireNonNull(candidates, "candidates");
    }
}
