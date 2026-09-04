package io.github.patricklfdm.generalsearch.durability;

/** Stable stage at which an offline migration failed. */
public enum DurableMigrationStage {
    VALIDATE_REQUEST,
    ACQUIRE_SOURCE,
    VERIFY_SOURCE,
    PROJECT_TARGET,
    VALIDATE_CAPACITY,
    PREPARE_TARGET,
    WRITE_METADATA,
    WRITE_CHECKPOINT,
    WRITE_MANIFEST,
    WRITE_WAL,
    VERIFY_STAGING,
    PUBLISH_TARGET,
    FORCE_PARENT,
    VERIFY_TARGET,
    VERIFY_SOURCE_PRESERVED,
    CLEANUP_MARKER,
    COMPLETE
}
