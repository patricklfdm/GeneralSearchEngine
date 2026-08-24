package io.github.patricklfdm.generalsearch.index;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;

/**
 * Immutable estimate of the candidate bitmap an index can safely produce.
 *
 * <p>Estimate quality describes cardinality precision. Candidate accuracy separately
 * describes whether the eventual bitmap is exact or a safe superset of query matches.</p>
 *
 * @param estimatedCandidateCardinality estimated number of candidate document IDs
 * @param estimatedSourceCount estimated number of value buckets or postings to visit
 * @param quality cardinality-estimate quality
 * @param accuracy accuracy of the eventual candidate bitmap
 */
public record CandidateEstimate(
        int estimatedCandidateCardinality,
        int estimatedSourceCount,
        EstimateQuality quality,
        CandidateAccuracy accuracy
) {
    public CandidateEstimate {
        if (estimatedCandidateCardinality < 0) {
            throw new IllegalArgumentException(
                    "estimatedCandidateCardinality must not be negative");
        }
        if (estimatedSourceCount < 0) {
            throw new IllegalArgumentException(
                    "estimatedSourceCount must not be negative");
        }
        Objects.requireNonNull(quality, "quality");
        Objects.requireNonNull(accuracy, "accuracy");
    }

    /**
     * Derives estimated selectivity for an active-document count.
     *
     * <p>The result is clamped to {@code [0, 1]}. A non-zero estimate against an empty
     * snapshot is conservatively reported as {@code 1.0}.</p>
     *
     * @param activeDocumentCount number of active documents in the associated snapshot
     * @return estimated candidate fraction in {@code [0, 1]}
     */
    public double selectivity(int activeDocumentCount) {
        if (activeDocumentCount < 0) {
            throw new IllegalArgumentException(
                    "activeDocumentCount must not be negative");
        }
        if (activeDocumentCount == 0) {
            return estimatedCandidateCardinality == 0 ? 0.0 : 1.0;
        }
        return Math.min(
                1.0,
                estimatedCandidateCardinality / (double) activeDocumentCount
        );
    }
}
