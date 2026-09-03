package io.github.patricklfdm.generalsearch.durability;

/** Exact offline authority boundary accepted by V4.1 cleanup. */
public enum DurableCleanupScope {
    /** One closed, structurally valid V4 live-store directory. */
    LIVE_STORE,
    /** One explicitly named V4.1 staging directory or sibling operation marker. */
    OPERATION_REMNANT
}
