package io.github.patricklfdm.generalsearch.durability;

/** Codec-free classification of optional V4.3 derived state. */
public enum DurableDerivedStateStatus {
    NOT_APPLICABLE,
    ABSENT,
    VALID,
    PARTIAL,
    STALE,
    INCOMPATIBLE,
    INCOMPLETE,
    CORRUPT
}
