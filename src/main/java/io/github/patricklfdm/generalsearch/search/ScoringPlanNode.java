package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.text.PhrasePositionAccess;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;

/** Package-private exact-match and score contract for prepared ranked nodes. */
sealed interface ScoringPlanNode<T> permits TextPlan, PhrasePlan, BoolPlan, BoostPlan {
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
        double normalization = config.k1() * (
                1.0 - config.b()
                        + config.b() * documentLength / averageDocumentLength
        );
        ScoreArithmetic.requireValid(normalization, "BM25 normalization");

        boolean matched = matchAlreadyEstablished;
        double score = 0.0;
        for (ScoringTerm term : scoringTerms) {
            int termFrequency = term.posting().termFrequency(docId);
            if (termFrequency == 0) {
                continue;
            }
            matched = true;
            double numerator = term.inverseDocumentFrequency()
                    * (termFrequency * (config.k1() + 1.0));
            ScoreArithmetic.requireValid(numerator, "BM25 numerator");
            double denominator = termFrequency + normalization;
            ScoreArithmetic.requireValid(denominator, "BM25 denominator");
            double termScore = numerator / denominator;
            ScoreArithmetic.requireValid(termScore, "BM25 term score");
            score = ScoreArithmetic.add(score, termScore);
        }
        return matched ? ScoreMatch.match(score) : ScoreMatch.noMatch();
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
