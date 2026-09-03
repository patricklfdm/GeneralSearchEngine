package io.github.patricklfdm.generalsearch.durability;

/** Stable codec-free structural-verification outcomes. */
public enum DurableVerificationStatus {
    /** Every authoritative member and the exact inventory are structurally valid. */
    VALID,
    /** Authority is valid and every reported remnant is proven non-authoritative. */
    VALID_WITH_SAFE_REMNANTS,
    /** A supported format is structurally valid but violates supported-minor policy. */
    INCOMPATIBLE,
    /** Required publication authority is absent or recognizably unfinished. */
    INCOMPLETE,
    /** Bytes claiming a supported format violate integrity or authority rules. */
    CORRUPT,
    /** An intact header declares an unsupported family or major format version. */
    UNSUPPORTED
}
