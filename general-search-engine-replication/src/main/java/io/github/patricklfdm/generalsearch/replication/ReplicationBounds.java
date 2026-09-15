package io.github.patricklfdm.generalsearch.replication;

/** Finite replication resource defaults and absolute limits. */
public record ReplicationBounds(
        int maxFrameBytes,
        int maxEntriesPerAppend,
        int maxInFlightPerPeer,
        int maxPendingClientOperations,
        int maxRetryAttempts,
        int requestTimeoutMillis,
        int retryBackoffMillis,
        int snapshotChunkBytes,
        long maxRetainedLogBytes,
        long maxSnapshotStagingBytes
) {
    public static final int HARD_MAX_FRAME_BYTES = 64 * 1024 * 1024;
    public static final int HARD_MAX_ENTRIES_PER_APPEND = 10_000;
    public static final int HARD_MAX_IN_FLIGHT_PER_PEER = 4096;
    public static final int HARD_MAX_PENDING_CLIENT_OPERATIONS = 100_000;
    public static final int HARD_MAX_RETRY_ATTEMPTS = 100;
    public static final int HARD_MAX_REQUEST_TIMEOUT_MILLIS = 300_000;
    public static final int HARD_MAX_RETRY_BACKOFF_MILLIS = 60_000;
    public static final int HARD_MAX_SNAPSHOT_CHUNK_BYTES = 64 * 1024 * 1024;
    public static final long HARD_MAX_RETAINED_LOG_BYTES = 1024L * 1024 * 1024 * 1024;
    public static final long HARD_MAX_SNAPSHOT_STAGING_BYTES = 1024L * 1024 * 1024 * 1024;

    /** Returns the Phase 1 frozen bounded defaults. */
    public static ReplicationBounds defaults() {
        return new ReplicationBounds(
                8 * 1024 * 1024,
                1000,
                256,
                10_000,
                12,
                5000,
                250,
                4 * 1024 * 1024,
                8L * 1024 * 1024 * 1024,
                16L * 1024 * 1024 * 1024);
    }

    public ReplicationBounds {
        positiveAtMost(maxFrameBytes, HARD_MAX_FRAME_BYTES, "maxFrameBytes");
        positiveAtMost(maxEntriesPerAppend, HARD_MAX_ENTRIES_PER_APPEND,
                "maxEntriesPerAppend");
        positiveAtMost(maxInFlightPerPeer, HARD_MAX_IN_FLIGHT_PER_PEER,
                "maxInFlightPerPeer");
        positiveAtMost(maxPendingClientOperations,
                HARD_MAX_PENDING_CLIENT_OPERATIONS, "maxPendingClientOperations");
        positiveAtMost(maxRetryAttempts, HARD_MAX_RETRY_ATTEMPTS,
                "maxRetryAttempts");
        positiveAtMost(requestTimeoutMillis, HARD_MAX_REQUEST_TIMEOUT_MILLIS,
                "requestTimeoutMillis");
        positiveAtMost(retryBackoffMillis, HARD_MAX_RETRY_BACKOFF_MILLIS,
                "retryBackoffMillis");
        positiveAtMost(snapshotChunkBytes, HARD_MAX_SNAPSHOT_CHUNK_BYTES,
                "snapshotChunkBytes");
        positiveAtMost(maxRetainedLogBytes, HARD_MAX_RETAINED_LOG_BYTES,
                "maxRetainedLogBytes");
        positiveAtMost(maxSnapshotStagingBytes, HARD_MAX_SNAPSHOT_STAGING_BYTES,
                "maxSnapshotStagingBytes");
    }

    private static void positiveAtMost(long value, long maximum, String name) {
        if (value < 1 || value > maximum) {
            throw new IllegalArgumentException(
                    name + " must be in [1, " + maximum + "]");
        }
    }
}
