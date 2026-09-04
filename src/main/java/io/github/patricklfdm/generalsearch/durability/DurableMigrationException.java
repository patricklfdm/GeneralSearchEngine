package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;
import java.util.OptionalLong;

/** Stable bounded failure raised by offline durable migration. */
public final class DurableMigrationException extends RuntimeException {
    /** Stable migration-specific reason order. */
    public enum Reason {
        STORAGE_IN_USE,
        SOURCE_INVALID,
        IDENTITY_MISMATCH,
        MIGRATION_PATH_UNSUPPORTED,
        MIGRATION_NOT_REQUIRED,
        PLAN_STALE,
        TRANSFORM_FAILURE,
        TRANSFORM_NONDETERMINISTIC,
        TARGET_EXISTS,
        TARGET_INVALID,
        UNSUPPORTED_FILESYSTEM,
        CAPACITY_EXCEEDED,
        IO_FAILURE,
        PUBLICATION_INDETERMINATE
    }

    private final Reason reason;
    private final DurableMigrationStage stage;
    private final OptionalLong sourceSequence;

    public DurableMigrationException(
            Reason reason,
            DurableMigrationStage stage,
            OptionalLong sourceSequence,
            Throwable cause
    ) {
        super(Objects.requireNonNull(reason, "reason").name(), cause);
        this.reason = reason;
        this.stage = Objects.requireNonNull(stage, "stage");
        this.sourceSequence = Objects.requireNonNull(sourceSequence, "sourceSequence");
        if (sourceSequence.isPresent() && sourceSequence.getAsLong() < 0) {
            throw new IllegalArgumentException("sourceSequence must not be negative");
        }
    }

    public Reason reason() {
        return reason;
    }

    public DurableMigrationStage stage() {
        return stage;
    }

    public OptionalLong sourceSequence() {
        return sourceSequence;
    }
}
