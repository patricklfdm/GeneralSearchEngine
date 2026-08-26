package io.github.patricklfdm.generalsearch.search;

import java.util.HashSet;
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
        TextIndexSnapshot<T> textIndex,
        List<ScoringTerm> scoringTerms,
        ImmutableBitmap candidates,
        Bm25Config config,
        double averageDocumentLength
) implements ScoringPlanNode<T> {
    TextPlan {
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
}

final class PhrasePlan<T> implements ScoringPlanNode<T> {
    private final TextIndexSnapshot<T> textIndex;
    private final List<ScoringTerm> scoringTerms;
    private final ImmutableBitmap candidates;
    private final Bm25Config config;
    private final double averageDocumentLength;
    private final int[] relativePositions;
    private final PostingList[][] alternativesBySlot;
    private final int anchorSlot;

    PhrasePlan(
            TextIndexSnapshot<T> textIndex,
            List<ScoringTerm> scoringTerms,
            ImmutableBitmap candidates,
            Bm25Config config,
            double averageDocumentLength,
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot
    ) {
        this.scoringTerms = List.copyOf(scoringTerms);
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
        if (this.relativePositions.length != this.alternativesBySlot.length) {
            throw new IllegalArgumentException(
                    "relative positions and alternative slots must have equal length");
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

    static <T> PhrasePlan<T> empty(Bm25Config config) {
        return new PhrasePlan<>(
                null,
                List.of(),
                ImmutableBitmap.empty(),
                config,
                0.0,
                new int[0],
                new PostingList[0][],
                -1
        );
    }

    @Override
    public ImmutableBitmap candidates() {
        return candidates;
    }

    @Override
    public ScoreMatch evaluate(int docId) {
        if (textIndex == null || !candidates.get(docId)) {
            return ScoreMatch.noMatch();
        }
        if (!PhrasePositionAccess.matches(
                docId,
                relativePositions,
                alternativesBySlot,
                anchorSlot
        )) {
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

    int anchorSlot() {
        return anchorSlot;
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
    private final TextIndexSnapshot<T> textIndex;
    private final String normalizedQueryTerm;
    private final List<FuzzyScoringExpansion> expansions;
    private final ImmutableBitmap candidates;
    private final Bm25Config config;
    private final double averageDocumentLength;

    FuzzyPlan(
            TextIndexSnapshot<T> textIndex,
            String normalizedQueryTerm,
            List<FuzzyScoringExpansion> expansions,
            ImmutableBitmap candidates,
            Bm25Config config,
            double averageDocumentLength
    ) {
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

    static <T> FuzzyPlan<T> empty(Bm25Config config) {
        return new FuzzyPlan<>(
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
}

record ScoringTerm(PostingList posting, double inverseDocumentFrequency) {
    ScoringTerm {
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
