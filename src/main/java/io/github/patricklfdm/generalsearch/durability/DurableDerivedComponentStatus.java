package io.github.patricklfdm.generalsearch.durability;

/** Independent admission result for one catalog-referenced index component. */
public enum DurableDerivedComponentStatus {
    ADMISSIBLE,
    MISSING,
    STALE,
    INCOMPATIBLE,
    INCOMPLETE,
    CORRUPT
}
