package io.github.patricklfdm.generalsearch.durability;

/** Stable typed backup-verification outcomes in deterministic precedence order. */
public enum DurableSemanticVerificationStatus {
    SEMANTICALLY_VALID,
    IDENTITY_MISMATCH,
    DECODE_FAILURE,
    STATE_MISMATCH
}
