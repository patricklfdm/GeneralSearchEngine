package io.github.patricklfdm.generalsearch.search;

/** Controls whether paged search computes the complete matching-document count. */
public enum TotalHitsMode {
    /** Do not expose a total-hit value. */
    DISABLED,

    /** Count every full query-and-filter match before page continuation and limit. */
    EXACT
}
