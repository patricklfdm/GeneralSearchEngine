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

    /**
     * Inspects a closed live store synchronously without loading a user codec.
     * The operation acquires exclusive ownership, is read-only, and retains an
     * intact unsupported or incompatible format declaration when available. Its
     * structural result does not claim semantic document validity.
     *
     * @param directory closed live-store directory
     * @return immutable format declaration and structural report
     */
    public static DurableStoreFormatReport inspectStoreFormat(Path directory) {
        return DurableStructuralVerifier.inspectStoreFormat(directory);
    }

    /**
     * Inspects an immutable backup bundle synchronously without loading a user
     * codec. Concurrent readers are supported; no byte is repaired or upgraded.
     * Declared backup/source formats remain explicit when their common header is
     * intact, while absence makes no semantic or default-format claim.
     *
     * @param directory completed backup-bundle directory
     * @return immutable format declarations and structural report
     */
    public static DurableBackupFormatReport inspectBackupFormat(Path directory) {
        return DurableStructuralVerifier.inspectBackupFormat(directory);
    }

    /**
     * Builds a codec-free, read-only cleanup plan for one exact offline boundary.
     * Planning acquires exclusive ownership, proves every candidate
     * non-authoritative, and binds the complete observed inventory. The returned plan
     * grants no permission after any filesystem or authority change.
     *
     * @param request exact live-store or operation-remnant request
     * @return deterministic immutable dry-run plan, possibly empty
     */
    public static DurableCleanupPlan planCleanup(DurableCleanupRequest request) {
        return DurableCleanupOperations.plan(request);
    }

    /**
     * Applies one previously produced cleanup plan synchronously and codec-free.
     * The operation reacquires exclusive ownership and rejects a stale plan before
     * deleting anything. Success proves each planned deletion was forced and the
     * surviving authority was reverified.
     *
     * @param plan exact dry-run plan to revalidate and apply
     * @return immutable deletion and post-verification result
     */
    public static DurableCleanupResult applyCleanup(DurableCleanupPlan plan) {
        return DurableCleanupOperations.apply(plan);
    }
}
