package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.FileAlreadyExistsException;
import java.nio.file.FileStore;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableRestoreResult;
import io.github.patricklfdm.generalsearch.durability.DurableSemanticVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationConfig;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

/** Internal publisher for a fresh same-format ordinary durable history. */
final class DurableRestoreWriter {
    private static final long OPERATION_MAGIC = 0x4753454f50313030L; // GSEOP100
    private static final byte RESTORE_OPERATION = 2;
    private static final long RESTORED_WAL_GENERATION = 2L;
    private static final Set<String> UNSUPPORTED_FILE_SYSTEM_MARKERS = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");

    private DurableRestoreWriter() {
    }

    static <K, T> DurableRestoreResult restore(
            Path backupDirectory,
            DurableStorageConfig<K, T> targetConfig,
            SearchSchema<T, K> schema,
            List<IndexDefinition<T>> startupDefinitions
    ) {
        Objects.requireNonNull(backupDirectory, "backupDirectory");
        Objects.requireNonNull(targetConfig, "targetConfig");
        Objects.requireNonNull(schema, "schema");
        Objects.requireNonNull(startupDefinitions, "startupDefinitions");
        Path backup = backupDirectory.toAbsolutePath().normalize();
        Target target = validateTarget(backup, targetConfig.directory());

        int codecVersion;
        try {
            codecVersion = targetConfig.codec().codecVersion();
        } catch (RuntimeException failure) {
            throw operation(DurableOperationException.Reason.IDENTITY_MISMATCH,
                    OptionalLong.empty(), failure);
        }
        DurableVerificationConfig<K, T> expected =
                new DurableVerificationConfig<>(
                        targetConfig.storageIdentity(),
                        targetConfig.schemaIdentity(),
                        targetConfig.codec(), codecVersion,
                        targetConfig.maxEncodedKeyBytes(),
                        targetConfig.maxEncodedDocumentBytes(),
                        targetConfig.maxDocuments());
        DurableSemanticOperations.Inspection<K, T> inspection =
                DurableSemanticOperations.inspect(backup, expected, schema,
                        startupDefinitions);
        if (inspection.report().status()
                != DurableSemanticVerificationStatus.SEMANTICALLY_VALID) {
            throw operation(DurableOperationException.Reason.IDENTITY_MISMATCH,
                    inspection.report().structuralReport().sequence(), null);
        }
        DurableStorageOwner.Metadata sourceMetadata = inspection.metadata();
        DurableFormatContext format = sourceMetadata.format();
        if (!targetConfig.format().equals(format.publicFormat())) {
            throw operation(DurableOperationException.Reason.IDENTITY_MISMATCH,
                    OptionalLong.of(inspection.authority().sequence()), null);
        }
        List<DurableIndexDescriptor> startupIndexes = startupDefinitions.stream()
                .map(DurableIndexDescriptor::from).toList();
        String codecIdentity = targetConfig.codec().codecId();
        try {
            DurableStorageOwner.validateMetadata(sourceMetadata, targetConfig,
                    codecIdentity, codecVersion, startupIndexes);
        } catch (DurabilityException failure) {
            throw operation(DurableOperationException.Reason.IDENTITY_MISMATCH,
                    OptionalLong.of(inspection.authority().sequence()), failure);
        }
        long sequence = inspection.authority().sequence();
        if (sequence == Long.MAX_VALUE) {
            throw new DurabilityException(
                    DurabilityException.Reason.SEQUENCE_EXHAUSTED,
                    sequence,
                    "restored sequence has no legal continuation");
        }

        UUID operationId = UUID.randomUUID();
        String compactId = operationId.toString().replace("-", "");
        String stagingName = ".gse-v41-restore-" + compactId + ".staging";
        Path staging = target.parent().resolve(stagingName);
        Path marker = target.parent().resolve(stagingName + ".operation");
        FileChannel markerChannel = null;
        FileLock markerLock = null;
        boolean markerCreated = false;
        boolean stagingCreated = false;
        boolean finalPublished = false;
        Throwable primary = null;
        try {
            preflight(target.parent(), targetConfig,
                    inspection.report().structuralReport().authoritativeBytes());
            markerChannel = FileChannel.open(marker, StandardOpenOption.CREATE_NEW,
                    StandardOpenOption.READ, StandardOpenOption.WRITE);
            markerCreated = true;
            markerLock = acquire(markerChannel, sequence);
            writeFully(markerChannel, ByteBuffer.wrap(encodeMarker(operationId,
                    stagingName, target.target().getFileName().toString())));
            DurableIoFaults.fail("v41-restore-before-marker-force");
            markerChannel.force(true);
            DurableStorageOwner.forceDirectory(target.parent());
            Files.createDirectory(staging);
            stagingCreated = true;
            DurableStorageOwner.forceDirectory(target.parent());
            DurableCrashHooks.reach("v41-restore-after-marker-force-v1");

            createLock(staging.resolve(DurableStorageOwner.LOCK_FILE));
            UUID newHistory = newHistory(inspection.authority().history());
            byte[] metadata = DurableStorageOwner.encodeMetadata(targetConfig,
                    codecIdentity, codecVersion, startupIndexes, newHistory);
            DurableStorageOwner.writeMetadata(staging, metadata);
            DurableCrashHooks.reach("v41-restore-after-metadata-force-v1");

            String checkpointFile = DurableCheckpoint.newCheckpointFile(sequence);
            Path checkpointStaging = staging.resolve(checkpointFile + ".staging");
            DurableCheckpoint.Capture<K, T> capture = new DurableCheckpoint.Capture<>(
                    inspection.recovered().snapshot(),
                    inspection.loaded().documentIds(),
                    inspection.loaded().nextDocId(), sequence,
                    inspection.loaded().indexes());
            DurableCheckpoint.Written written = DurableCheckpoint.write(
                    checkpointStaging, capture, targetConfig, schema, format,
                    newHistory,
                    targetConfig.maxRetainedBytes());
            moveAtomic(checkpointStaging, staging.resolve(checkpointFile));
            DurableCrashHooks.reach("v41-restore-after-checkpoint-rename-v1");

            long firstSequence = sequence + 1;
            String walFile = DurableStorageOwner.walFile(
                    RESTORED_WAL_GENERATION);
            try (DurableWal ignored = DurableWal.create(staging.resolve(walFile),
                    format, newHistory, RESTORED_WAL_GENERATION, firstSequence)) {
                // create() forces the canonical empty generation header.
            }
            DurableCrashHooks.reach("v41-restore-after-wal-force-v1");

            DurableCheckpoint.Manifest manifest = new DurableCheckpoint.Manifest(
                    sequence, checkpointFile, written.bytes(), written.checksum(),
                    RESTORED_WAL_GENERATION, firstSequence);
            Path manifestStaging = staging.resolve(
                    DurableCheckpoint.MANIFEST_STAGING_FILE);
            try (FileChannel channel = FileChannel.open(manifestStaging,
                    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                writeFully(channel, ByteBuffer.wrap(
                        DurableCheckpoint.encodeManifest(
                                manifest, format, newHistory)));
                DurableIoFaults.fail("v41-restore-before-manifest-force");
                channel.force(true);
            }
            DurableCrashHooks.reach("v41-restore-after-manifest-force-v1");
            moveAtomic(manifestStaging,
                    staging.resolve(DurableCheckpoint.MANIFEST_FILE));
            DurableStorageOwner.forceDirectory(staging);
            DurableCrashHooks.reach("v41-restore-after-manifest-rename-v1");

            DurableVerificationReport staged = requireValidStore(staging, sequence);
            validateTypedTarget(staging, targetConfig, schema, startupIndexes,
                    newHistory, manifest, inspection.loaded());
            if (staged.authoritativeBytes() > targetConfig.maxRetainedBytes()) {
                throw operation(DurableOperationException.Reason.CAPACITY_EXCEEDED,
                        OptionalLong.of(sequence), null);
            }

            DurableCrashHooks.reach("v41-restore-before-final-rename-v1");
            if (Files.exists(target.target(), LinkOption.NOFOLLOW_LINKS)) {
                throw operation(DurableOperationException.Reason.TARGET_EXISTS,
                        OptionalLong.of(sequence), null);
            }
            moveAtomic(staging, target.target());
            finalPublished = true;
            DurableCrashHooks.reach("v41-restore-after-final-rename-v1");
            DurableStorageOwner.forceDirectory(target.parent());
            DurableCrashHooks.reach("v41-restore-after-parent-force-v1");
            DurableVerificationReport completed = requireValidStore(
                    target.target(), sequence);
            validateTypedTarget(target.target(), targetConfig, schema,
                    startupIndexes, newHistory, manifest, inspection.loaded());

            closeMarker(markerLock, markerChannel, null);
            markerLock = null;
            markerChannel = null;
            DurableIoFaults.fail("v41-restore-before-marker-delete");
            Files.delete(marker);
            DurableStorageOwner.forceDirectory(target.parent());
            requireValidStore(target.target(), sequence);
            DurableCrashHooks.reach("v41-restore-before-return-v1");
            return new DurableRestoreResult(target.target(), newHistory,
                    inspection.authority().history(),
                    inspection.authority().contentIdentity(), sequence,
                    completed.authoritativeBytes());
        } catch (DurableOperationException | DurabilityException failure) {
            primary = failure;
            throw failure;
        } catch (AtomicMoveNotSupportedException failure) {
            DurableOperationException wrapped = operation(
                    DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                    OptionalLong.of(sequence), failure);
            primary = wrapped;
            throw wrapped;
        } catch (FileAlreadyExistsException failure) {
            DurableOperationException wrapped = operation(
                    DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                    OptionalLong.of(sequence), failure);
            primary = wrapped;
            throw wrapped;
        } catch (ArithmeticException failure) {
            DurabilityException wrapped = new DurabilityException(
                    DurabilityException.Reason.SEQUENCE_EXHAUSTED, sequence,
                    "restored sequence has no legal continuation", failure);
            primary = wrapped;
            throw wrapped;
        } catch (IOException failure) {
            DurableOperationException wrapped = operation(
                    DurableOperationException.Reason.IO_FAILURE,
                    OptionalLong.of(sequence), failure);
            primary = wrapped;
            throw wrapped;
        } finally {
            closeMarker(markerLock, markerChannel, primary);
            if (!finalPublished) {
                cleanup(staging, marker, stagingCreated, markerCreated, primary);
            }
        }
    }

    private static <K, T> void validateTypedTarget(
            Path directory,
            DurableStorageConfig<K, T> config,
            SearchSchema<T, K> schema,
            List<DurableIndexDescriptor> startupIndexes,
            UUID history,
            DurableCheckpoint.Manifest manifest,
            DurableCheckpoint.Loaded<K, T> source
    ) throws IOException {
        DurableStorageOwner.Metadata metadata = DurableStorageOwner.readMetadata(
                directory.resolve(DurableStorageOwner.METADATA_FILE));
        DurableStorageOwner.validateMetadata(metadata, config,
                config.codec().codecId(), config.codec().codecVersion(),
                startupIndexes);
        DurableCheckpoint.Manifest rereadManifest = DurableCheckpoint.readManifest(
                directory.resolve(DurableCheckpoint.MANIFEST_FILE),
                metadata.format(), history);
        if (!rereadManifest.equals(manifest)) {
            throw new DurabilityException(
                    DurabilityException.Reason.CORRUPT_CHECKPOINT,
                    "restored manifest changed during typed validation");
        }
        DurableWal.Header wal = DurableWal.inspectHeader(
                directory.resolve(DurableStorageOwner.walFile(
                        RESTORED_WAL_GENERATION)), metadata.format(), history);
        if (wal.generation() != RESTORED_WAL_GENERATION
                || wal.firstSequence() != manifest.walFirstSequence()) {
            throw new DurabilityException(DurabilityException.Reason.CORRUPT_WAL,
                    "restored WAL identity is invalid");
        }
        DurableCheckpoint.Loaded<K, T> loaded = DurableCheckpoint.read(
                directory.resolve(manifest.checkpointFile()), config, schema,
                metadata.format(), history, manifest);
        DurableRecovery.Result<K, T> recovered = DurableRecovery.replay(config,
                schema, startupIndexes, loaded, List.of(), false);
        if (loaded.sequence() != source.sequence()
                || loaded.nextDocId() != source.nextDocId()
                || !loaded.documentIds().equals(source.documentIds())
                || !loaded.indexes().equals(source.indexes())
                || recovered.snapshot().activeDocuments().cardinality()
                        != source.documentIds().size()) {
            throw new DurabilityException(
                    DurabilityException.Reason.REPLAY_FAILURE,
                    "restored typed state differs from its source backup");
        }
    }

    private static DurableVerificationReport requireValidStore(
            Path directory, long sequence) {
        DurableVerificationReport report =
                DurableStorageOperations.verifyStore(directory);
        if (report.status() != DurableVerificationStatus.VALID
                || report.sequence().isEmpty()
                || report.sequence().getAsLong() != sequence) {
            throw operation(DurableOperationException.Reason.TARGET_INVALID,
                    OptionalLong.of(sequence), null);
        }
        return report;
    }

    private static Target validateTarget(Path backup, Path configuredTarget) {
        Path target = Objects.requireNonNull(configuredTarget, "targetDirectory")
                .toAbsolutePath().normalize();
        if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            throw operation(DurableOperationException.Reason.TARGET_EXISTS,
                    OptionalLong.empty(), null);
        }
        Path requestedParent = target.getParent();
        if (requestedParent == null || Files.isSymbolicLink(requestedParent)
                || !Files.isDirectory(requestedParent,
                        LinkOption.NOFOLLOW_LINKS)) {
            throw operation(DurableOperationException.Reason.TARGET_INVALID,
                    OptionalLong.empty(), null);
        }
        try {
            Path parent = requestedParent.toRealPath(LinkOption.NOFOLLOW_LINKS);
            Path resolved = parent.resolve(target.getFileName()).normalize();
            if (!resolved.equals(target) || resolved.startsWith(backup)
                    || backup.startsWith(resolved)) {
                throw operation(DurableOperationException.Reason.TARGET_INVALID,
                        OptionalLong.empty(), null);
            }
            validateFileSystem(parent);
            return new Target(parent, resolved);
        } catch (DurableOperationException failure) {
            throw failure;
        } catch (IOException failure) {
            throw operation(DurableOperationException.Reason.IO_FAILURE,
                    OptionalLong.empty(), failure);
        }
    }

    private static void preflight(Path parent, DurableStorageConfig<?, ?> config,
                                  long sourceBytes) throws IOException {
        long estimate = Math.max(sourceBytes, 1L);
        if (estimate > config.maxRetainedBytes()
                || Files.getFileStore(parent).getUsableSpace() < estimate) {
            throw operation(DurableOperationException.Reason.CAPACITY_EXCEEDED,
                    OptionalLong.empty(), null);
        }
    }

    private static UUID newHistory(UUID source) {
        UUID candidate;
        do {
            candidate = UUID.randomUUID();
        } while (candidate.equals(new UUID(0L, 0L)) || candidate.equals(source));
        return candidate;
    }

    private static void createLock(Path path) throws IOException {
        try (FileChannel channel = FileChannel.open(path,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.READ,
                StandardOpenOption.WRITE)) {
            channel.force(true);
        }
    }

    private static byte[] encodeMarker(UUID operationId, String stagingName,
                                       String targetName) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        CRC32C checksum = new CRC32C();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(OPERATION_MAGIC);
            output.writeShort(1);
            output.writeShort(0);
            output.writeByte(RESTORE_OPERATION);
            output.writeLong(operationId.getMostSignificantBits());
            output.writeLong(operationId.getLeastSignificantBits());
            writeString(output, stagingName);
            writeString(output, targetName);
            output.flush();
            checksum.update(bytes.toByteArray());
            output.writeInt((int) checksum.getValue());
        }
        return bytes.toByteArray();
    }

    private static void validateFileSystem(Path directory) throws IOException {
        FileStore store = Files.getFileStore(directory);
        String type = store.type().toLowerCase(Locale.ROOT);
        for (String marker : UNSUPPORTED_FILE_SYSTEM_MARKERS) {
            if (type.contains(marker)) {
                throw operation(
                        DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                        OptionalLong.empty(), null);
            }
        }
    }

    private static FileLock acquire(FileChannel channel, long sequence)
            throws IOException {
        try {
            FileLock lock = channel.tryLock();
            if (lock == null) {
                throw operation(
                        DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                        OptionalLong.of(sequence), null);
            }
            return lock;
        } catch (OverlappingFileLockException failure) {
            throw operation(DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                    OptionalLong.of(sequence), failure);
        }
    }

    private static void moveAtomic(Path source, Path target) throws IOException {
        Files.move(source, target, StandardCopyOption.ATOMIC_MOVE);
    }

    private static void writeFully(FileChannel channel, ByteBuffer bytes)
            throws IOException {
        while (bytes.hasRemaining()) {
            if (DurableIoFaults.write(channel, bytes) <= 0) {
                throw new IOException("restore write made no progress");
            }
        }
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        output.writeInt(encoded.length);
        output.write(encoded);
    }

    private static void closeMarker(FileLock lock, FileChannel channel,
                                    Throwable primary) {
        if (lock != null) {
            try {
                lock.close();
            } catch (IOException failure) {
                suppress(primary, failure);
            }
        }
        if (channel != null) {
            try {
                channel.close();
            } catch (IOException failure) {
                suppress(primary, failure);
            }
        }
    }

    private static void cleanup(Path staging, Path marker,
                                boolean stagingCreated, boolean markerCreated,
                                Throwable primary) {
        try {
            if (stagingCreated && Files.isDirectory(staging,
                    LinkOption.NOFOLLOW_LINKS) && !Files.isSymbolicLink(staging)) {
                try (var members = Files.list(staging)) {
                    for (Path member : members.toList()) {
                        if (!Files.isDirectory(member, LinkOption.NOFOLLOW_LINKS)) {
                            Files.deleteIfExists(member);
                        }
                    }
                }
                Files.deleteIfExists(staging);
            }
            if (markerCreated) {
                Files.deleteIfExists(marker);
            }
            if (stagingCreated || markerCreated) {
                DurableStorageOwner.forceDirectory(marker.getParent());
            }
        } catch (IOException | RuntimeException failure) {
            suppress(primary, failure);
        }
    }

    private static void suppress(Throwable primary, Throwable later) {
        if (primary != null) {
            primary.addSuppressed(later);
        }
    }

    private static DurableOperationException operation(
            DurableOperationException.Reason reason,
            OptionalLong sequence,
            Throwable cause) {
        return new DurableOperationException(reason, sequence, cause);
    }

    private record Target(Path parent, Path target) {
    }
}
