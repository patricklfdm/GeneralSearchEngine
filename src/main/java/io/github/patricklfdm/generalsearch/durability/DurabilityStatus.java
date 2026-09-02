package io.github.patricklfdm.generalsearch.durability;

/** Durable writer lifecycle visible through {@link DurabilityMetrics}. */
public enum DurabilityStatus {
    /** The engine accepts durable mutations. */
    OPEN,
    /** Admission is blocked by the configured retained-byte limit. */
    CAPACITY_BLOCKED,
    /** A terminal storage failure prevents further mutation. */
    FAILED,
    /** The durable engine has been closed. */
    CLOSED
}
