package io.github.patricklfdm.generalsearch.query;

import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimateQuality;

/** Internal relative-work model; constants are intentionally not public API. */
final class PlannerCostModel {
    private static final int MIN_COSTED_DOCUMENTS = 64;
    private static final double SCAN_DOCUMENT_WORK = 1.0;
    private static final double CANDIDATE_DOCUMENT_WORK = 8.0;
    private static final double SOURCE_WORK = 2.0;
    private static final double APPROXIMATE_PENALTY = 1.25;

    boolean preferIndex(CandidateEstimate estimate, int activeDocumentCount) {
        if (activeDocumentCount < MIN_COSTED_DOCUMENTS) {
            return true;
        }
        return accessPathWork(estimate) <= activeDocumentCount * SCAN_DOCUMENT_WORK;
    }

    double accessPathWork(CandidateEstimate estimate) {
        double work = estimate.estimatedCandidateCardinality()
                * CANDIDATE_DOCUMENT_WORK
                + estimate.estimatedSourceCount() * SOURCE_WORK;
        return estimate.quality() == EstimateQuality.APPROXIMATE
                ? work * APPROXIMATE_PENALTY
                : work;
    }

    boolean intersectionPays(
            CandidateEstimate estimate,
            int currentCandidateCardinality
    ) {
        if (estimate.quality() != EstimateQuality.EXACT
                || estimate.estimatedCandidateCardinality()
                >= currentCandidateCardinality) {
            return false;
        }
        int guaranteedVerificationSavings = currentCandidateCardinality
                - estimate.estimatedCandidateCardinality();
        double bitmapIntersectionWork = Math.ceil(
                estimate.estimatedCandidateCardinality() / 64.0
        ) + estimate.estimatedSourceCount() * SOURCE_WORK;
        return bitmapIntersectionWork < guaranteedVerificationSavings;
    }
}
