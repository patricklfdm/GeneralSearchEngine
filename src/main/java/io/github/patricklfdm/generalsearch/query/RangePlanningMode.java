package io.github.patricklfdm.generalsearch.query;

/** Selects how direct range queries choose between an index and a full scan. */
public enum RangePlanningMode {
    /** Compares snapshot-local index estimates with the active-document scan cost. */
    COST_AWARE,

    /** Uses the least-cost estimated range index whenever one is available. */
    FORCE_INDEX,

    /** Bypasses range indexes and verifies every active document. */
    FORCE_SCAN
}
