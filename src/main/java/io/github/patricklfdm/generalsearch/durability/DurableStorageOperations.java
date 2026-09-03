package io.github.patricklfdm.generalsearch.durability;

import java.nio.file.Path;

/** Codec-free offline operations over V4 durable stores and V4.1 backup bundles. */
public final class DurableStorageOperations {
    private DurableStorageOperations() {
    }

    /**
     * Structurally verifies a closed V4 durable store without recovery or mutation.
     * The method is synchronous and requires exclusive acquisition of its V4 lock.
     * A {@link DurableVerificationStatus#VALID} result proves byte and authority
     * structure only; it makes no document-decode or retrieval claim.
     *
     * @param directory closed live-store directory
     * @return immutable structural report
     */
    public static DurableVerificationReport verifyStore(Path directory) {
        return DurableStructuralVerifier.verifyStore(directory);
    }

    /**
     * Structurally verifies an immutable V4.1 backup bundle without a user codec.
     * The synchronous operation is read-only and supports concurrent bundle readers.
     * A {@link DurableVerificationStatus#VALID} result proves byte, inventory,
     * checksum, content-identity, history and sequence structure only.
     *
     * @param directory completed backup-bundle directory
     * @return immutable structural report
     */
    public static DurableVerificationReport verifyBackup(Path directory) {
        return DurableStructuralVerifier.verifyBackup(directory);
    }
}
