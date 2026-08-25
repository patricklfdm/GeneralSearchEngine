package io.github.patricklfdm.generalsearch.engine.exception;

import java.util.Objects;

/** Raised when an explicit atomic mutation collection is structurally invalid. */
public final class BulkMutationException extends IllegalArgumentException {
    /** Stable reason for rejecting the complete explicit bulk operation. */
    public enum Reason {
        DUPLICATE_ID,
        TOO_LARGE
    }

    private final Reason reason;
    private final Object documentId;
    private final int batchSize;
    private final int maximumBatchSize;

    private BulkMutationException(
            Reason reason,
            Object documentId,
            int batchSize,
            int maximumBatchSize
    ) {
        super(message(reason, documentId, batchSize, maximumBatchSize));
        this.reason = Objects.requireNonNull(reason, "reason");
        this.documentId = documentId;
        this.batchSize = batchSize;
        this.maximumBatchSize = maximumBatchSize;
    }

    public Reason reason() {
        return reason;
    }

    /** Returns the duplicate business ID, or {@code null} for a size rejection. */
    public Object documentId() {
        return documentId;
    }

    public int batchSize() {
        return batchSize;
    }

    public int maximumBatchSize() {
        return maximumBatchSize;
    }

    public static BulkMutationException duplicateId(
            Object documentId,
            int batchSize,
            int maximumBatchSize
    ) {
        return new BulkMutationException(
                Reason.DUPLICATE_ID,
                Objects.requireNonNull(documentId, "documentId"),
                batchSize,
                maximumBatchSize);
    }

    public static BulkMutationException tooLarge(int batchSize, int maximumBatchSize) {
        return new BulkMutationException(
                Reason.TOO_LARGE,
                null,
                batchSize,
                maximumBatchSize);
    }

    private static String message(
            Reason reason,
            Object documentId,
            int batchSize,
            int maximumBatchSize
    ) {
        return switch (Objects.requireNonNull(reason, "reason")) {
            case DUPLICATE_ID -> "duplicate document ID in atomic bulk mutation: "
                    + documentId;
            case TOO_LARGE -> "atomic bulk mutation size " + batchSize
                    + " exceeds configured maximum " + maximumBatchSize;
        };
    }
}
