package io.github.patricklfdm.generalsearch.durability;

/** Authoritative source used to construct the ready in-memory state. */
public enum RecoverySource {
    /** A newly initialized empty history. */
    FRESH,
    /** WAL history without an authoritative checkpoint. */
    WAL_ONLY,
    /** An authoritative checkpoint with no later WAL units. */
    CHECKPOINT_ONLY,
    /** An authoritative checkpoint followed by WAL units. */
    CHECKPOINT_AND_WAL
}
