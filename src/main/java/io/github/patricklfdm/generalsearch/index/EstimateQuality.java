package io.github.patricklfdm.generalsearch.index;

/** Describes whether a candidate-cardinality estimate is exact or approximate. */
public enum EstimateQuality {
    /** The reported cardinality equals the candidate bitmap cardinality. */
    EXACT,

    /** The reported cardinality is an approximation used only for cost comparison. */
    APPROXIMATE
}
