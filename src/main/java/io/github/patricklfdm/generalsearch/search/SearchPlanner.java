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
        this(filterPlanner, new VocabularyScanningFuzzyTermExpander());
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
        if (!input.hasNonEmptyScoringLeaf()) {
            return SearchPlan.empty(input);
        }

        ScoringPlanNode<T> root = compile(input.root(), input.config());
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
            return new BoolPlan<>(must, should, boolCandidates(must, should));
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
                    null,
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
            double inverseDocumentFrequency = Math.log1p(
                    (documentCount - documentFrequency + 0.5)
                            / (documentFrequency + 0.5)
            );
            scoringTerms.add(new ScoringTerm(
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
                textIndex,
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
            return PhrasePlan.empty(config);
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
                    posting,
                    inverseDocumentFrequency(documentCount, documentFrequency)
            ));
        }

        return new PhrasePlan<>(
                textIndex,
                scoringTerms,
                candidates,
                config,
                textIndex.averageDocumentLength(),
                relativePositions,
                alternativesBySlot,
                anchorSlot
        );
    }

    private FuzzyPlan<T> compileFuzzy(
            NormalizedFuzzyNode<T> fuzzy,
            Bm25Config config
    ) {
        if (fuzzy.normalizedTerm() == null) {
            return FuzzyPlan.empty(config);
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
                            expansion.posting(),
                            inverseDocumentFrequency(
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

    private double inverseDocumentFrequency(
            int documentCount,
            int documentFrequency
    ) {
        return Math.log1p(
                (documentCount - documentFrequency + 0.5)
                        / (documentFrequency + 0.5)
        );
    }

    private ImmutableBitmap boolCandidates(
            List<ScoringPlanNode<T>> must,
            List<ScoringPlanNode<T>> should
    ) {
        if (!must.isEmpty()) {
            List<ScoringPlanNode<T>> physical = new ArrayList<>(must);
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

        ImmutableBitmap first = null;
        ImmutableBitmapBuilder union = null;
        for (ScoringPlanNode<T> child : should) {
            if (first == null) {
                first = child.candidates();
            } else {
                if (union == null) {
                    union = new ImmutableBitmapBuilder(first);
                }
                union.or(child.candidates());
            }
        }
        if (first == null) {
            return ImmutableBitmap.empty();
        }
        return union == null ? first : union.build();
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
