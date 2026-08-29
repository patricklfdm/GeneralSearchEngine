package io.github.patricklfdm.generalsearch.search;

import java.util.HashSet;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.text.PhrasePositionAccess;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;

/** Package-private exact-match and score contract for prepared ranked nodes. */
sealed interface ScoringPlanNode<T>
        permits TextPlan, PhrasePlan, FuzzyPlan, BoolPlan, BoostPlan {
    ImmutableBitmap candidates();

    ScoreMatch evaluate(int docId);

    ExplanationNode explain(int docId);
}

record ScoreMatch(boolean matched, double score) {
    private static final ScoreMatch NO_MATCH = new ScoreMatch(false, 0.0);

    ScoreMatch {
        if (!Double.isFinite(score) || score < 0.0) {
            throw new ArithmeticException(
                    "ranked score must be finite and non-negative: " + score);
        }
        if (!matched && score != 0.0) {
            throw new IllegalArgumentException("a non-match cannot carry a score");
        }
        if (score == 0.0) {
            score = 0.0;
        }
    }

    static ScoreMatch noMatch() {
        return NO_MATCH;
    }

    static ScoreMatch match(double score) {
        return new ScoreMatch(true, score);
    }
}

record TextPlan<T>(
        String fieldName,
        TextIndexSnapshot<T> textIndex,
        List<String> diagnosticTerms,
        List<ScoringTerm> scoringTerms,
        ImmutableBitmap candidates,
        Bm25Config config,
        double averageDocumentLength
) implements ScoringPlanNode<T> {
    TextPlan {
        Objects.requireNonNull(fieldName, "fieldName");
        diagnosticTerms = List.copyOf(diagnosticTerms);
        scoringTerms = List.copyOf(scoringTerms);
        if (textIndex == null && !scoringTerms.isEmpty()) {
            throw new IllegalArgumentException(
                    "an empty text plan cannot carry scoring terms");
        }
        Objects.requireNonNull(candidates, "candidates");
        Objects.requireNonNull(config, "config");
        if (!Double.isFinite(averageDocumentLength)
                || averageDocumentLength < 0.0) {
            throw new IllegalArgumentException(
                    "average document length must be finite and non-negative");
        }
    }

    @Override
    public ScoreMatch evaluate(int docId) {
        if (textIndex == null) {
            return ScoreMatch.noMatch();
        }
        return Bm25Scorer.evaluate(
                textIndex,
                scoringTerms,
                config,
                averageDocumentLength,
                docId,
                false
        );
    }

    @Override
    public ExplanationNode explain(int docId) {
        if (textIndex == null) {
            return ExplanationSupport.node(
                    ScoreMatch.noMatch(),
                    "TEXT field=" + ExplanationSupport.quote(fieldName)
                            + " analysis produced no scoring terms",
                    List.of()
            );
        }
        ScoreMatch result = evaluate(docId);
        List<ExplanationNode> children = ExplanationSupport.bm25Terms(
                fieldName,
                textIndex,
                diagnosticTerms,
                scoringTerms,
                config,
                averageDocumentLength,
                docId
        );
        return ExplanationSupport.node(
                result,
                "TEXT field=" + ExplanationSupport.quote(fieldName),
                children
        );
    }
}

final class PhrasePlan<T> implements ScoringPlanNode<T> {
    private final String fieldName;
    private final TextIndexSnapshot<T> textIndex;
    private final List<ScoringTerm> scoringTerms;
    private final List<String> diagnosticScoringTerms;
    private final ImmutableBitmap candidates;
    private final Bm25Config config;
    private final double averageDocumentLength;
    private final int[] relativePositions;
    private final PostingList[][] alternativesBySlot;
    private final int anchorSlot;
    private final List<PhraseSlot> diagnosticSlots;
    private final int requestedSlop;

    PhrasePlan(
            String fieldName,
            TextIndexSnapshot<T> textIndex,
            List<ScoringTerm> scoringTerms,
            List<String> diagnosticScoringTerms,
            ImmutableBitmap candidates,
            Bm25Config config,
            double averageDocumentLength,
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot,
            List<PhraseSlot> diagnosticSlots,
            int requestedSlop
    ) {
        this.fieldName = Objects.requireNonNull(fieldName, "fieldName");
        if (requestedSlop < 0) {
            throw new IllegalArgumentException(
                    "requestedSlop must not be negative");
        }
        this.requestedSlop = requestedSlop;
        this.scoringTerms = List.copyOf(scoringTerms);
        this.diagnosticScoringTerms = List.copyOf(diagnosticScoringTerms);
        this.candidates = Objects.requireNonNull(candidates, "candidates");
        this.config = Objects.requireNonNull(config, "config");
        if (!Double.isFinite(averageDocumentLength)
                || averageDocumentLength < 0.0) {
            throw new IllegalArgumentException(
                    "average document length must be finite and non-negative");
        }
        this.averageDocumentLength = averageDocumentLength;
        this.relativePositions = Objects.requireNonNull(
                relativePositions,
                "relativePositions"
        ).clone();
        this.alternativesBySlot = copyAlternatives(alternativesBySlot);
        this.diagnosticSlots = List.copyOf(diagnosticSlots);
        if (this.relativePositions.length != this.alternativesBySlot.length) {
            throw new IllegalArgumentException(
                    "relative positions and alternative slots must have equal length");
        }
        if (this.relativePositions.length != this.diagnosticSlots.size()) {
            throw new IllegalArgumentException(
                    "relative positions and diagnostic slots must have equal length");
        }
        if (this.relativePositions.length == 0) {
            if (textIndex != null || !this.scoringTerms.isEmpty() || anchorSlot != -1) {
                throw new IllegalArgumentException(
                        "an empty phrase plan cannot carry prepared scoring state");
            }
        } else {
            Objects.requireNonNull(textIndex, "textIndex");
            validateSlots(this.relativePositions, this.alternativesBySlot, anchorSlot);
        }
        this.textIndex = textIndex;
        this.anchorSlot = anchorSlot;
    }

    static <T> PhrasePlan<T> empty(
            String fieldName,
            Bm25Config config,
            int requestedSlop
    ) {
        return new PhrasePlan<>(
                fieldName,
                null,
                List.of(),
                List.of(),
                ImmutableBitmap.empty(),
                config,
                0.0,
                new int[0],
                new PostingList[0][],
                -1,
                List.of(),
                requestedSlop
        );
    }

    @Override
    public ImmutableBitmap candidates() {
        return candidates;
    }

    @Override
    public ScoreMatch evaluate(int docId) {
        long consumedSlop = consumedSlop(docId);
        if (consumedSlop < 0L) {
            return ScoreMatch.noMatch();
        }
        return Bm25Scorer.evaluate(
                textIndex,
                scoringTerms,
                config,
                averageDocumentLength,
                docId,
                true
        );
    }

    @Override
    public ExplanationNode explain(int docId) {
        if (textIndex == null) {
            return ExplanationSupport.node(
                    ScoreMatch.noMatch(),
                    "PHRASE field=" + ExplanationSupport.quote(fieldName)
                            + " requestedSlop=" + requestedSlop
                            + " analysis produced no phrase slots",
                    List.of()
            );
        }
        long consumedSlop = consumedSlop(docId);
        ScoreMatch result = consumedSlop < 0L
                ? ScoreMatch.noMatch()
                : Bm25Scorer.evaluate(
                        textIndex,
                        scoringTerms,
                        config,
                        averageDocumentLength,
                        docId,
                        true
                );
        ExplanationNode relation = new ExplanationNode(
                result.matched(),
                0.0,
                "ordered analyzed relative-position pattern "
                        + (result.matched() ? "matched " : "did not match ")
                        + ExplanationSupport.phrasePattern(diagnosticSlots)
                        + " requestedSlop=" + requestedSlop
                        + (result.matched()
                                ? " minimumConsumedSlop=" + consumedSlop
                                : ""),
                List.of()
        );
        List<ExplanationNode> children = new ArrayList<>();
        children.add(relation);
        if (result.matched()) {
            children.addAll(ExplanationSupport.bm25Terms(
                    fieldName,
                    textIndex,
                    diagnosticScoringTerms,
                    scoringTerms,
                    config,
                    averageDocumentLength,
                    docId
            ));
        }
        return ExplanationSupport.node(
                result,
                "PHRASE field=" + ExplanationSupport.quote(fieldName)
                        + " requestedSlop=" + requestedSlop,
                children
        );
    }

    int anchorSlot() {
        return anchorSlot;
    }

    int requestedSlop() {
        return requestedSlop;
    }

    private long consumedSlop(int docId) {
        if (textIndex == null || !candidates.get(docId)) {
            return -1L;
        }
        if (requestedSlop == 0) {
            return PhrasePositionAccess.matches(
                    docId,
                    relativePositions,
                    alternativesBySlot,
                    anchorSlot
            ) ? 0L : -1L;
        }
        return PhrasePositionAccess.minimumConsumedSlop(
                docId,
                relativePositions,
                alternativesBySlot,
                anchorSlot,
                requestedSlop
        );
    }

    private static PostingList[][] copyAlternatives(PostingList[][] supplied) {
        Objects.requireNonNull(supplied, "alternativesBySlot");
        PostingList[][] copy = new PostingList[supplied.length][];
        for (int slot = 0; slot < supplied.length; slot++) {
            copy[slot] = Objects.requireNonNull(
                    supplied[slot],
                    "alternativesBySlot[" + slot + "]"
            ).clone();
            for (int alternative = 0;
                    alternative < copy[slot].length;
                    alternative++) {
                Objects.requireNonNull(
                        copy[slot][alternative],
                        "alternativesBySlot[" + slot + "][" + alternative + "]"
                );
            }
        }
        return copy;
    }

    private static void validateSlots(
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot
    ) {
        if (anchorSlot < 0 || anchorSlot >= relativePositions.length) {
            throw new IllegalArgumentException("anchorSlot is out of range");
        }
        int previousPosition = -1;
        for (int slot = 0; slot < relativePositions.length; slot++) {
            if (slot == 0 && relativePositions[slot] != 0) {
                throw new IllegalArgumentException(
                        "the first relative position must be zero");
            }
            if (relativePositions[slot] <= previousPosition) {
                throw new IllegalArgumentException(
                        "relative positions must be strictly increasing");
            }
            if (alternativesBySlot[slot].length == 0) {
                throw new IllegalArgumentException(
                        "every phrase slot requires at least one alternative");
            }
            previousPosition = relativePositions[slot];
        }
    }
}

final class FuzzyPlan<T> implements ScoringPlanNode<T> {
    private final String fieldName;
    private final TextIndexSnapshot<T> textIndex;
    private final String normalizedQueryTerm;
    private final List<FuzzyScoringExpansion> expansions;
    private final ImmutableBitmap candidates;
    private final Bm25Config config;
    private final double averageDocumentLength;

    FuzzyPlan(
            String fieldName,
            TextIndexSnapshot<T> textIndex,
            String normalizedQueryTerm,
            List<FuzzyScoringExpansion> expansions,
            ImmutableBitmap candidates,
            Bm25Config config,
            double averageDocumentLength
    ) {
        this.fieldName = Objects.requireNonNull(fieldName, "fieldName");
        this.expansions = List.copyOf(expansions);
        this.candidates = Objects.requireNonNull(candidates, "candidates");
        this.config = Objects.requireNonNull(config, "config");
        if (!Double.isFinite(averageDocumentLength)
                || averageDocumentLength < 0.0) {
            throw new IllegalArgumentException(
                    "average document length must be finite and non-negative");
        }
        this.averageDocumentLength = averageDocumentLength;
        if (normalizedQueryTerm == null) {
            if (textIndex != null
                    || !this.expansions.isEmpty()
                    || !candidates.isEmpty()) {
                throw new IllegalArgumentException(
                        "an empty fuzzy plan cannot carry prepared scoring state");
            }
        } else {
            if (normalizedQueryTerm.isEmpty()) {
                throw new IllegalArgumentException(
                        "normalizedQueryTerm must not be empty");
            }
            Objects.requireNonNull(textIndex, "textIndex");
            validateExpansions(normalizedQueryTerm, this.expansions);
        }
        this.textIndex = textIndex;
        this.normalizedQueryTerm = normalizedQueryTerm;
    }

    static <T> FuzzyPlan<T> empty(String fieldName, Bm25Config config) {
        return new FuzzyPlan<>(
                fieldName,
                null,
                null,
                List.of(),
                ImmutableBitmap.empty(),
                config,
                0.0
        );
    }

    @Override
    public ImmutableBitmap candidates() {
        return candidates;
    }

    @Override
    public ScoreMatch evaluate(int docId) {
        return evaluateFuzzy(docId).result();
    }

    @Override
    public ExplanationNode explain(int docId) {
        if (textIndex == null) {
            return ExplanationSupport.node(
                    ScoreMatch.noMatch(),
                    "FUZZY field=" + ExplanationSupport.quote(fieldName)
                            + " analysis produced no query term",
                    List.of()
            );
        }
        int queryLength = normalizedQueryTerm.codePointCount(
                0,
                normalizedQueryTerm.length()
        );
        int maxEdits = BoundedOptimalStringAlignment.autoMaxEdits(
                normalizedQueryTerm
        );
        FuzzyEvaluation evaluation = evaluateFuzzy(docId);
        String prefix = "FUZZY field=" + ExplanationSupport.quote(fieldName)
                + " query=" + ExplanationSupport.quote(normalizedQueryTerm)
                + " codePointLength=" + queryLength
                + " autoMaxEdits=" + maxEdits;
        if (!evaluation.result().matched()) {
            String reason = expansions.isEmpty()
                    ? " no indexed term is within the allowed edit threshold"
                    : " no expanded term matches this document";
            return ExplanationSupport.node(
                    evaluation.result(),
                    prefix + reason,
                    List.of()
            );
        }

        FuzzyScoringExpansion selected = expansions.stream()
                .filter(expansion -> expansion.term().equals(
                        evaluation.selectedTerm()))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException(
                        "selected fuzzy expansion is not prepared"));
        int documentLength = textIndex.documentLength(docId);
        int termFrequency = selected.scoringTerm().posting().termFrequency(docId);
        double bm25 = 0.0;
        if (documentLength != 0 && averageDocumentLength != 0.0) {
            double normalization = Bm25Scorer.normalization(
                    config,
                    averageDocumentLength,
                    documentLength
            );
            bm25 = Bm25Scorer.termScore(
                    selected.scoringTerm(),
                    termFrequency,
                    config,
                    normalization
            );
        }
        String priority = selected.editDistance() == 0
                ? " exact-term priority"
                : " best weighted expansion";
        ExplanationNode selectedNode = new ExplanationNode(
                true,
                evaluation.result().score(),
                "selected term=" + ExplanationSupport.quote(selected.term())
                        + priority
                        + " editDistance=" + selected.editDistance()
                        + " similarity=" + selected.similarity()
                        + " tf=" + termFrequency
                        + " df=" + selected.scoringTerm().posting()
                                .documentFrequency()
                        + " N=" + textIndex.statistics().indexedDocumentCount()
                        + " dl=" + documentLength
                        + " avgdl=" + averageDocumentLength
                        + " k1=" + config.k1()
                        + " b=" + config.b()
                        + " idf=" + selected.scoringTerm()
                                .inverseDocumentFrequency()
                        + " bm25=" + bm25
                        + " weighted=" + evaluation.result().score(),
                List.of()
        );
        return ExplanationSupport.node(
                evaluation.result(),
                prefix,
                List.of(selectedNode)
        );
    }

    FuzzyEvaluation evaluateFuzzy(int docId) {
        if (textIndex == null || !candidates.get(docId)) {
            return FuzzyEvaluation.noMatch();
        }

        int documentLength = textIndex.documentLength(docId);
        double normalization = averageDocumentLength == 0.0 || documentLength == 0
                ? 0.0
                : Bm25Scorer.normalization(
                        config,
                        averageDocumentLength,
                        documentLength
                );
        for (FuzzyScoringExpansion expansion : expansions) {
            if (expansion.editDistance() != 0) {
                break;
            }
            int termFrequency = expansion.scoringTerm()
                    .posting()
                    .termFrequency(docId);
            if (termFrequency > 0) {
                double score = documentLength == 0 || averageDocumentLength == 0.0
                        ? 0.0
                        : Bm25Scorer.termScore(
                                expansion.scoringTerm(),
                                termFrequency,
                                config,
                                normalization
                        );
                return FuzzyEvaluation.match(score, expansion.term());
            }
        }

        boolean matched = false;
        double bestScore = 0.0;
        String selectedTerm = null;
        for (FuzzyScoringExpansion expansion : expansions) {
            if (expansion.editDistance() == 0) {
                continue;
            }
            int termFrequency = expansion.scoringTerm()
                    .posting()
                    .termFrequency(docId);
            if (termFrequency == 0) {
                continue;
            }
            double termScore = documentLength == 0 || averageDocumentLength == 0.0
                    ? 0.0
                    : Bm25Scorer.termScore(
                            expansion.scoringTerm(),
                            termFrequency,
                            config,
                            normalization
                    );
            double weightedScore = ScoreArithmetic.multiply(
                    termScore,
                    expansion.similarity()
            );
            if (!matched || Double.compare(weightedScore, bestScore) > 0) {
                matched = true;
                bestScore = weightedScore;
                selectedTerm = expansion.term();
            }
        }
        return matched
                ? FuzzyEvaluation.match(bestScore, selectedTerm)
                : FuzzyEvaluation.noMatch();
    }

    String normalizedQueryTerm() {
        return normalizedQueryTerm;
    }

    List<FuzzyScoringExpansion> expansions() {
        return expansions;
    }

    private static void validateExpansions(
            String normalizedQueryTerm,
            List<FuzzyScoringExpansion> expansions
    ) {
        Set<String> terms = new HashSet<>();
        FuzzyScoringExpansion previous = null;
        for (FuzzyScoringExpansion expansion : expansions) {
            if (!terms.add(expansion.term())) {
                throw new IllegalArgumentException(
                        "fuzzy expansions must contain unique terms");
            }
            if ((expansion.editDistance() == 0)
                    != expansion.term().equals(normalizedQueryTerm)) {
                throw new IllegalArgumentException(
                        "only the normalized query term may have distance zero");
            }
            if (previous != null) {
                int comparison = Integer.compare(
                        previous.editDistance(),
                        expansion.editDistance()
                );
                if (comparison > 0
                        || (comparison == 0
                        && BoundedOptimalStringAlignment.compareCodePoints(
                                previous.term(),
                                expansion.term()
                        ) >= 0)) {
                    throw new IllegalArgumentException(
                            "fuzzy expansions must use deterministic order");
                }
            }
            previous = expansion;
        }
    }
}

record BoolPlan<T>(
        List<ScoringPlanNode<T>> must,
        List<ScoringPlanNode<T>> should,
        ImmutableBitmap candidates
) implements ScoringPlanNode<T> {
    BoolPlan {
        must = List.copyOf(must);
        should = List.copyOf(should);
        Objects.requireNonNull(candidates, "candidates");
    }

    @Override
    public ScoreMatch evaluate(int docId) {
        double score = 0.0;
        for (ScoringPlanNode<T> child : must) {
            ScoreMatch result = child.evaluate(docId);
            if (!result.matched()) {
                return ScoreMatch.noMatch();
            }
            score = ScoreArithmetic.add(score, result.score());
        }

        boolean anyShouldMatched = false;
        for (ScoringPlanNode<T> child : should) {
            ScoreMatch result = child.evaluate(docId);
            if (result.matched()) {
                anyShouldMatched = true;
                score = ScoreArithmetic.add(score, result.score());
            }
        }
        if (must.isEmpty() && !anyShouldMatched) {
            return ScoreMatch.noMatch();
        }
        return ScoreMatch.match(score);
    }

    @Override
    public ExplanationNode explain(int docId) {
        ScoreMatch result = evaluate(docId);
        List<ExplanationNode> children = new ArrayList<>(must.size() + should.size());
        for (ScoringPlanNode<T> child : must) {
            ExplanationNode detail = child.explain(docId);
            children.add(new ExplanationNode(
                    detail.matched(),
                    detail.score(),
                    "MUST clause",
                    List.of(detail)
            ));
        }
        for (ScoringPlanNode<T> child : should) {
            ExplanationNode detail = child.explain(docId);
            children.add(new ExplanationNode(
                    detail.matched(),
                    detail.score(),
                    "SHOULD clause",
                    List.of(detail)
            ));
        }
        return ExplanationSupport.node(result, "BOOL ranked query", children);
    }
}

record BoostPlan<T>(
        ScoringPlanNode<T> child,
        double multiplier
) implements ScoringPlanNode<T> {
    BoostPlan {
        Objects.requireNonNull(child, "child");
        if (!Double.isFinite(multiplier) || multiplier <= 0.0) {
            throw new IllegalArgumentException("boost must be finite and positive");
        }
    }

    @Override
    public ImmutableBitmap candidates() {
        return child.candidates();
    }

    @Override
    public ScoreMatch evaluate(int docId) {
        ScoreMatch result = child.evaluate(docId);
        return result.matched()
                ? ScoreMatch.match(ScoreArithmetic.multiply(
                        result.score(),
                        multiplier
                ))
                : ScoreMatch.noMatch();
    }

    @Override
    public ExplanationNode explain(int docId) {
        ScoreMatch result = evaluate(docId);
        return ExplanationSupport.node(
                result,
                "BOOST multiplier=" + multiplier,
                List.of(child.explain(docId))
        );
    }
}

record ScoringTerm(
        String term,
        PostingList posting,
        double inverseDocumentFrequency
) {
    ScoringTerm {
        Objects.requireNonNull(term, "term");
        if (term.isEmpty()) {
            throw new IllegalArgumentException("term must not be empty");
        }
        Objects.requireNonNull(posting, "posting");
        ScoreArithmetic.requireValid(
                inverseDocumentFrequency,
                "inverse document frequency"
        );
    }
}

record FuzzyScoringExpansion(
        String term,
        ScoringTerm scoringTerm,
        int editDistance,
        double similarity
) {
    FuzzyScoringExpansion {
        Objects.requireNonNull(term, "term");
        Objects.requireNonNull(scoringTerm, "scoringTerm");
        if (term.isEmpty()) {
            throw new IllegalArgumentException("term must not be empty");
        }
        if (editDistance < 0
                || editDistance > BoundedOptimalStringAlignment.MAX_AUTO_EDITS) {
            throw new IllegalArgumentException(
                    "editDistance must be between 0 and 2");
        }
        ScoreArithmetic.requireValid(similarity, "fuzzy similarity");
        if (similarity > 1.0) {
            throw new ArithmeticException(
                    "fuzzy similarity must not be greater than 1: " + similarity);
        }
    }
}

record FuzzyEvaluation(ScoreMatch result, String selectedTerm) {
    private static final FuzzyEvaluation NO_MATCH = new FuzzyEvaluation(
            ScoreMatch.noMatch(),
            null
    );

    FuzzyEvaluation {
        Objects.requireNonNull(result, "result");
        if (result.matched() != (selectedTerm != null)) {
            throw new IllegalArgumentException(
                    "selectedTerm must be present exactly when fuzzy matched");
        }
    }

    static FuzzyEvaluation noMatch() {
        return NO_MATCH;
    }

    static FuzzyEvaluation match(double score, String selectedTerm) {
        return new FuzzyEvaluation(
                ScoreMatch.match(score),
                Objects.requireNonNull(selectedTerm, "selectedTerm")
        );
    }
}

final class Bm25Scorer {
    private Bm25Scorer() {
    }

    static ScoreMatch evaluate(
            TextIndexSnapshot<?> textIndex,
            List<ScoringTerm> scoringTerms,
            Bm25Config config,
            double averageDocumentLength,
            int docId,
            boolean matchAlreadyEstablished
    ) {
        int documentLength = textIndex.documentLength(docId);
        if (averageDocumentLength == 0.0 || documentLength == 0) {
            return matchAlreadyEstablished
                    ? ScoreMatch.match(0.0)
                    : ScoreMatch.noMatch();
        }
        double normalization = normalization(
                config,
                averageDocumentLength,
                documentLength
        );

        boolean matched = matchAlreadyEstablished;
        double score = 0.0;
        for (ScoringTerm term : scoringTerms) {
            int termFrequency = term.posting().termFrequency(docId);
            if (termFrequency == 0) {
                continue;
            }
            matched = true;
            double termScore = termScore(
                    term,
                    termFrequency,
                    config,
                    normalization
            );
            score = ScoreArithmetic.add(score, termScore);
        }
        return matched ? ScoreMatch.match(score) : ScoreMatch.noMatch();
    }

    static double normalization(
            Bm25Config config,
            double averageDocumentLength,
            int documentLength
    ) {
        double normalization = config.k1() * (
                1.0 - config.b()
                        + config.b() * documentLength / averageDocumentLength
        );
        return ScoreArithmetic.requireValid(normalization, "BM25 normalization");
    }

    static double inverseDocumentFrequency(
            int documentCount,
            int documentFrequency
    ) {
        return ScoreArithmetic.requireValid(
                Math.log1p(
                        (documentCount - documentFrequency + 0.5)
                                / (documentFrequency + 0.5)
                ),
                "inverse document frequency"
        );
    }

    static double termScore(
            ScoringTerm term,
            int termFrequency,
            Bm25Config config,
            double normalization
    ) {
        double numerator = term.inverseDocumentFrequency()
                * (termFrequency * (config.k1() + 1.0));
        ScoreArithmetic.requireValid(numerator, "BM25 numerator");
        double denominator = termFrequency + normalization;
        ScoreArithmetic.requireValid(denominator, "BM25 denominator");
        double termScore = numerator / denominator;
        return ScoreArithmetic.requireValid(termScore, "BM25 term score");
    }
}

final class ScoreArithmetic {
    private ScoreArithmetic() {
    }

    static double add(double left, double right) {
        return requireValid(left + right, "score addition");
    }

    static double multiply(double left, double right) {
        return requireValid(left * right, "score multiplication");
    }

    static double requireValid(double value, String operation) {
        if (!Double.isFinite(value) || value < 0.0) {
            throw new ArithmeticException(
                    operation + " produced an invalid score: " + value);
        }
        return value == 0.0 ? 0.0 : value;
    }
}

final class ExplanationSupport {
    private ExplanationSupport() {
    }

    static ExplanationNode node(
            ScoreMatch result,
            String description,
            List<ExplanationNode> children
    ) {
        return new ExplanationNode(
                result.matched(),
                result.score(),
                description,
                children
        );
    }

    static List<ExplanationNode> bm25Terms(
            String fieldName,
            TextIndexSnapshot<?> textIndex,
            List<String> diagnosticTerms,
            List<ScoringTerm> scoringTerms,
            Bm25Config config,
            double averageDocumentLength,
            int docId
    ) {
        int documentLength = textIndex.documentLength(docId);
        int documentCount = textIndex.statistics().indexedDocumentCount();
        double normalization = averageDocumentLength == 0.0 || documentLength == 0
                ? 0.0
                : Bm25Scorer.normalization(
                        config,
                        averageDocumentLength,
                        documentLength
                );
        List<ExplanationNode> children = new ArrayList<>(diagnosticTerms.size());
        for (String diagnosticTerm : diagnosticTerms) {
            ScoringTerm term = null;
            for (ScoringTerm prepared : scoringTerms) {
                if (prepared.term().equals(diagnosticTerm)) {
                    term = prepared;
                    break;
                }
            }
            if (term == null) {
                PostingList posting = textIndex.posting(diagnosticTerm);
                term = new ScoringTerm(
                        diagnosticTerm,
                        posting,
                        Bm25Scorer.inverseDocumentFrequency(
                                documentCount,
                                posting.documentFrequency()
                        )
                );
            }
            int termFrequency = term.posting().termFrequency(docId);
            boolean matched = termFrequency > 0;
            double contribution = matched
                    && documentLength != 0
                    && averageDocumentLength != 0.0
                    ? Bm25Scorer.termScore(
                            term,
                            termFrequency,
                            config,
                            normalization
                    )
                    : 0.0;
            children.add(new ExplanationNode(
                    matched,
                    contribution,
                    "BM25 term=" + quote(term.term())
                            + " field=" + quote(fieldName)
                            + " tf=" + termFrequency
                            + " df=" + term.posting().documentFrequency()
                            + " N=" + documentCount
                            + " dl=" + documentLength
                            + " avgdl=" + averageDocumentLength
                            + " k1=" + config.k1()
                            + " b=" + config.b()
                            + " idf=" + term.inverseDocumentFrequency()
                            + " contribution=" + contribution,
                    List.of()
            ));
        }
        return List.copyOf(children);
    }

    static String phrasePattern(List<PhraseSlot> slots) {
        StringBuilder pattern = new StringBuilder("slots=[");
        for (int slotIndex = 0; slotIndex < slots.size(); slotIndex++) {
            if (slotIndex > 0) {
                pattern.append(", ");
            }
            PhraseSlot slot = slots.get(slotIndex);
            pattern.append(slot.relativePosition()).append(':');
            for (int alternative = 0;
                    alternative < slot.alternatives().size();
                    alternative++) {
                if (alternative > 0) {
                    pattern.append('|');
                }
                pattern.append(quote(slot.alternatives().get(alternative)));
            }
        }
        return pattern.append(']').toString();
    }

    static String quote(String value) {
        Objects.requireNonNull(value, "value");
        StringBuilder escaped = new StringBuilder(value.length() + 2).append('"');
        value.codePoints().forEach(codePoint -> {
            switch (codePoint) {
                case '\\' -> escaped.append("\\\\");
                case '"' -> escaped.append("\\\"");
                case '\n' -> escaped.append("\\n");
                case '\r' -> escaped.append("\\r");
                case '\t' -> escaped.append("\\t");
                default -> escaped.appendCodePoint(codePoint);
            }
        });
        return escaped.append('"').toString();
    }
}
