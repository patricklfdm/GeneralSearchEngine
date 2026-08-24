package io.github.patricklfdm.generalsearch.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import org.junit.jupiter.api.Test;

class CandidateEstimateTest {
    @Test
    void derivesBoundedSelectivityWithoutStoringSnapshotSize() {
        CandidateEstimate estimate = new CandidateEstimate(
                25,
                3,
                EstimateQuality.EXACT,
                CandidateAccuracy.SUPERSET
        );

        assertEquals(0.25, estimate.selectivity(100));
        assertEquals(1.0, estimate.selectivity(10));
        assertEquals(1.0, estimate.selectivity(0));
        assertEquals(0.0, new CandidateEstimate(
                0,
                0,
                EstimateQuality.APPROXIMATE,
                CandidateAccuracy.EXACT
        ).selectivity(0));
    }

    @Test
    void rejectsInvalidCountsAndActiveDocumentCount() {
        assertThrows(IllegalArgumentException.class, () -> new CandidateEstimate(
                -1, 0, EstimateQuality.EXACT, CandidateAccuracy.EXACT));
        assertThrows(IllegalArgumentException.class, () -> new CandidateEstimate(
                0, -1, EstimateQuality.EXACT, CandidateAccuracy.EXACT));
        assertThrows(IllegalArgumentException.class,
                () -> new IndexStatistics(-1, 0));
        assertThrows(IllegalArgumentException.class,
                () -> new IndexStatistics(0, -1));

        CandidateEstimate estimate = new CandidateEstimate(
                0, 0, EstimateQuality.EXACT, CandidateAccuracy.EXACT);
        assertThrows(IllegalArgumentException.class, () -> estimate.selectivity(-1));
    }
}
