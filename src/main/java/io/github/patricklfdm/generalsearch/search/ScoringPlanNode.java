package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;

/** Package-private exact-match and score contract for prepared ranked nodes. */
sealed interface ScoringPlanNode<T> permits TextPlan, BoolPlan, BoostPlan {
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
        int documentLength = textIndex.documentLength(docId);
        if (averageDocumentLength == 0.0 || documentLength == 0) {
            return ScoreMatch.noMatch();
        }
        double normalization = config.k1() * (
                1.0 - config.b()
                        + config.b() * documentLength / averageDocumentLength
        );
        ScoreArithmetic.requireValid(normalization, "BM25 normalization");

        boolean matched = false;
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
