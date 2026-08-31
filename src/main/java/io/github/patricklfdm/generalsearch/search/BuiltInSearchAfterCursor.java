package io.github.patricklfdm.generalsearch.search;

import java.util.Objects;

/** Private constant-sized cursor used only by the built-in snapshot engine. */
final class BuiltInSearchAfterCursor implements SearchAfterCursor {
    private final Object ownerToken;
    private final SearchRequest<?> searchRequest;
    private final long snapshotVersion;
    private final long scoreBits;
    private final int documentId;

    BuiltInSearchAfterCursor(
            Object ownerToken,
            SearchRequest<?> searchRequest,
            long snapshotVersion,
            double score,
            int documentId
    ) {
        this.ownerToken = Objects.requireNonNull(ownerToken, "ownerToken");
        this.searchRequest = Objects.requireNonNull(
                searchRequest,
                "searchRequest"
        );
        if (snapshotVersion < 0L) {
            throw new IllegalArgumentException(
                    "snapshotVersion must not be negative");
        }
        if (!Double.isFinite(score) || score < 0.0) {
            throw new IllegalArgumentException(
                    "score must be finite and non-negative");
        }
        if (documentId < 0) {
            throw new IllegalArgumentException(
                    "documentId must not be negative");
        }
        this.snapshotVersion = snapshotVersion;
        this.scoreBits = Double.doubleToRawLongBits(score);
        this.documentId = documentId;
    }

    boolean belongsTo(Object expectedOwnerToken) {
        return ownerToken == expectedOwnerToken;
    }

    boolean wraps(SearchRequest<?> expectedRequest) {
        return searchRequest == expectedRequest;
    }

    boolean captures(long expectedSnapshotVersion) {
        return snapshotVersion == expectedSnapshotVersion;
    }

    PageAnchor anchor() {
        return new PageAnchor(
                Double.longBitsToDouble(scoreBits),
                documentId
        );
    }
}

record PageAnchor(double score, int documentId) {
    PageAnchor {
        if (!Double.isFinite(score) || score < 0.0) {
            throw new IllegalArgumentException(
                    "score must be finite and non-negative");
        }
        if (documentId < 0) {
            throw new IllegalArgumentException(
                    "documentId must not be negative");
        }
    }
}
