package io.github.patricklfdm.generalsearch.durability;

/** High-level result of optional derived-state admission during durable reopen. */
public enum DurableReopenOutcome {
    NOT_APPLICABLE,
    COMPLETE_WARM,
    PARTIAL_FALLBACK,
    FULL_FALLBACK
}
