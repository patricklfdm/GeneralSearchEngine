package io.github.patricklfdm.generalsearch.replication;

/** Explicit read guarantees; a lower bound does not imply global freshness. */
public enum ReplicaReadPolicy {
    /** Fresh quorum barrier on the ready leader. */
    LEADER_STRONG,
    /** Any locally published committed prefix, potentially arbitrarily old. */
    STALE_ALLOWED,
    /** A compatible published prefix at or beyond the supplied log position. */
    AT_LEAST_INDEX
}
