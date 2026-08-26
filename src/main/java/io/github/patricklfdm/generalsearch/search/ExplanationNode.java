package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;

/**
 * Immutable generic node in a ranked-search explanation tree.
 *
 * <p>Descriptions are deterministic human-readable diagnostics, not a stable
 * parseable format. Applications should use the structured match, score, and child
 * values instead of parsing description text.</p>
 */
public final class ExplanationNode {
    private final boolean matched;
    private final double score;
    private final String description;
    private final List<ExplanationNode> children;

    /**
     * Creates an explanation node.
     *
     * @param matched whether this node matched
     * @param score finite non-negative score, zero when unmatched
     * @param description non-null human-readable description
     * @param children non-null child list containing no null element
     * @throws NullPointerException when {@code description}, {@code children}, or one
     *         child is null
     * @throws IllegalArgumentException when the score is invalid or non-zero while
     *         unmatched
     */
    public ExplanationNode(
            boolean matched,
            double score,
            String description,
            List<ExplanationNode> children
    ) {
        validateScore(matched, score);
        this.matched = matched;
        this.score = score;
        this.description = Objects.requireNonNull(description, "description");
        this.children = List.copyOf(children);
    }

    /** @return whether this explanation node matched */
    public boolean matched() {
        return matched;
    }

    /** @return this node's finite non-negative score */
    public double score() {
        return score;
    }

    /** @return the non-null human-readable description */
    public String description() {
        return description;
    }

    /** @return the immutable ordered child list */
    public List<ExplanationNode> children() {
        return children;
    }

    static void validateScore(boolean matched, double score) {
        if (!Double.isFinite(score) || score < 0.0) {
            throw new IllegalArgumentException("score must be finite and non-negative");
        }
        if (!matched && score != 0.0) {
            throw new IllegalArgumentException("an unmatched explanation must score zero");
        }
    }
}
