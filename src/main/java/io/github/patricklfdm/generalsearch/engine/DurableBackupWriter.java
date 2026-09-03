package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
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
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.OptionalLong;
import java.util.Set;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurableBackupFormat;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.durability.DurableBackupResult;
import io.github.patricklfdm.generalsearch.durability.DurableOperationException;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurableStorageOperations;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationReport;
import io.github.patricklfdm.generalsearch.durability.DurableVerificationStatus;

/** Internal writer for the immutable {@code gse-backup (1,0)} bundle. */
final class DurableBackupWriter {
    private static final long BACKUP_MAGIC = 0x475345424b503130L; // GSEBKP10
    private static final long OPERATION_MAGIC = 0x4753454f50313030L; // GSEOP100
    private static final short FORMAT_MAJOR = 1;
    private static final short FORMAT_MINOR = 0;
    private static final byte BACKUP_OPERATION = 1;
    private static final String BACKUP_FAMILY = "gse-backup";
    private static final String SOURCE_FAMILY = "gse-durable";
    private static final String METADATA = "gse-backup-metadata";
    private static final String CHECKPOINT = "gse-backup-checkpoint";
    private static final String MANIFEST = "gse-backup-manifest";
    private static final List<String> PAYLOAD_ORDER = List.of(CHECKPOINT, METADATA);
    private static final byte[] CONTENT_DOMAIN =
            "gse-backup-content-v1\0".getBytes(StandardCharsets.US_ASCII);
    private static final int COPY_BUFFER_BYTES = 64 * 1024;
    private static final int MAX_MANIFEST_BYTES = 16 * 1024 * 1024;
    private static final Set<String> UNSUPPORTED_FILE_SYSTEM_MARKERS = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");
    private static final Set<String> OWNED_STAGING_MEMBERS = Set.of(
            METADATA, CHECKPOINT, MANIFEST, MANIFEST + ".staging");

    private DurableBackupWriter() {
    }

    static Target validateTarget(Path sourceDirectory, DurableBackupRequest request) {
        Objects.requireNonNull(sourceDirectory, "sourceDirectory");
        Objects.requireNonNull(request, "request");
        Path source = sourceDirectory.toAbsolutePath().normalize();
        Path target = request.targetDirectory();
        if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            throw failure(DurableOperationException.Reason.TARGET_EXISTS, null, null);
        }
        Path requestedParent = target.getParent();
        if (requestedParent == null
                || Files.isSymbolicLink(requestedParent)
                || !Files.isDirectory(requestedParent, LinkOption.NOFOLLOW_LINKS)) {
            throw failure(DurableOperationException.Reason.TARGET_INVALID, null, null);
        }
        try {
            Path parent = requestedParent.toRealPath(LinkOption.NOFOLLOW_LINKS);
            Path resolvedTarget = parent.resolve(target.getFileName()).normalize();
            if (!resolvedTarget.equals(target)
                    || resolvedTarget.startsWith(source)
                    || source.startsWith(resolvedTarget)) {
                throw failure(DurableOperationException.Reason.TARGET_INVALID,
                        null, null);
            }
            validateFileSystem(parent);
            return new Target(parent, resolvedTarget);
        } catch (DurableOperationException exception) {
            throw exception;
        } catch (IOException exception) {
            throw failure(DurableOperationException.Reason.IO_FAILURE,
                    null, exception);
        }
    }

    static <K, T> DurableBackupResult write(
            Path sourceDirectory,
            String checkpointFile,
            UUID history,
            long sequence,
            DurableStorageConfig<K, T> config,
            String codecIdentity,
            int codecVersion,
            DurableBackupRequest request
    ) {
        Target target = validateTarget(sourceDirectory, request);
        UUID operationId = UUID.randomUUID();
        String compactId = operationId.toString().replace("-", "");
        String stagingName = ".gse-v41-backup-" + compactId + ".staging";
        Path staging = target.parent().resolve(stagingName);
        Path marker = target.parent().resolve(stagingName + ".operation");
        FileChannel markerChannel = null;
        FileLock markerLock = null;
        boolean markerCreated = false;
        boolean stagingCreated = false;
        boolean finalPublished = false;
        Throwable primary = null;
        try {
            requireSourceMember(sourceDirectory.resolve(
                    DurableStorageOwner.METADATA_FILE));
            requireSourceMember(sourceDirectory.resolve(checkpointFile));
            if (Files.exists(staging, LinkOption.NOFOLLOW_LINKS)
                    || Files.exists(marker, LinkOption.NOFOLLOW_LINKS)) {
                throw failure(DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                        sequence, null);
            }
            try {
                markerChannel = FileChannel.open(marker,
                        StandardOpenOption.CREATE_NEW,
                        StandardOpenOption.READ,
                        StandardOpenOption.WRITE);
                markerCreated = true;
            } catch (FileAlreadyExistsException collision) {
                throw failure(
                        DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                        sequence, collision);
            }
            markerLock = acquireMarkerLock(markerChannel, sequence);
            writeFully(markerChannel, ByteBuffer.wrap(encodeOperationMarker(
                    operationId, stagingName, target.target().getFileName().toString())));
            DurableIoFaults.fail("v41-backup-before-marker-force");
            markerChannel.force(true);
            forceDirectory(target.parent());
            try {
                Files.createDirectory(staging);
                stagingCreated = true;
            } catch (FileAlreadyExistsException collision) {
                throw failure(
                        DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                        sequence, collision);
            }
            forceDirectory(target.parent());
            DurableCrashHooks.reach("v41-backup-after-marker-force-v1");

            long estimatedPayloadBytes = Math.addExact(
                    Files.size(sourceDirectory.resolve(DurableStorageOwner.METADATA_FILE)),
                    Files.size(sourceDirectory.resolve(checkpointFile)));
            if (estimatedPayloadBytes <= 0
                    || estimatedPayloadBytes > request.maxBundleBytes()
                    || Files.size(sourceDirectory.resolve(checkpointFile))
                            > config.maxRetainedBytes()) {
                throw failure(DurableOperationException.Reason.CAPACITY_EXCEEDED,
                        sequence, null);
            }
            if (Files.getFileStore(target.parent()).getUsableSpace()
                    < estimatedPayloadBytes) {
                throw failure(DurableOperationException.Reason.CAPACITY_EXCEEDED,
                        sequence, null);
            }

            List<Payload> payloads = new ArrayList<>(2);
            payloads.add(copyPayload(
                    sourceDirectory.resolve(DurableStorageOwner.METADATA_FILE),
                    staging.resolve(METADATA), METADATA,
                    "v41-backup-during-metadata-copy-v1",
                    "v41-backup-after-metadata-force-v1"));
            payloads.add(copyPayload(
                    sourceDirectory.resolve(checkpointFile),
                    staging.resolve(CHECKPOINT), CHECKPOINT,
                    "v41-backup-during-checkpoint-copy-v1",
                    "v41-backup-after-checkpoint-force-v1"));
            payloads.sort(Comparator.comparing(Payload::name));
            long payloadBytes = payloads.stream().mapToLong(Payload::size)
                    .reduce(0L, Math::addExact);
            byte[] contentDigest = contentDigest(history, sequence, config,
                    codecIdentity, codecVersion, payloads);
            String contentIdentity = "gse-backup-v1-"
                    + HexFormat.of().formatHex(contentDigest);
            byte[] manifestBytes = encodeManifest(history, sequence, config,
                    codecIdentity, codecVersion, payloads, contentDigest,
                    System.currentTimeMillis(), compactId);
            long totalBytes = Math.addExact(payloadBytes, manifestBytes.length);
            if (manifestBytes.length > MAX_MANIFEST_BYTES
                    || totalBytes > request.maxBundleBytes()) {
                throw failure(DurableOperationException.Reason.CAPACITY_EXCEEDED,
                        sequence, null);
            }

            Path manifestStaging = staging.resolve(MANIFEST + ".staging");
            try (FileChannel channel = FileChannel.open(manifestStaging,
                    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                writeFully(channel, ByteBuffer.wrap(manifestBytes));
                DurableIoFaults.fail("v41-backup-before-manifest-force");
                channel.force(true);
            }
            DurableCrashHooks.reach("v41-backup-after-manifest-force-v1");
            moveAtomic(manifestStaging, staging.resolve(MANIFEST));
            DurableCrashHooks.reach("v41-backup-after-manifest-rename-v1");
            forceDirectory(staging);
            requireValidBundle(staging, sequence);

            DurableCrashHooks.reach("v41-backup-before-final-rename-v1");
            DurableIoFaults.fail("v41-backup-before-final-rename");
            if (Files.exists(target.target(), LinkOption.NOFOLLOW_LINKS)) {
                throw failure(DurableOperationException.Reason.TARGET_EXISTS,
                        sequence, null);
            }
            moveAtomic(staging, target.target());
            finalPublished = true;
            DurableCrashHooks.reach("v41-backup-after-final-rename-v1");
            DurableIoFaults.fail("v41-backup-before-parent-force");
            forceDirectory(target.parent());
            DurableCrashHooks.reach("v41-backup-after-parent-force-v1");
            requireValidBundle(target.target(), sequence);

            closeMarker(markerLock, markerChannel, null);
            markerLock = null;
            markerChannel = null;
            DurableIoFaults.fail("v41-backup-before-marker-delete");
            Files.delete(marker);
            forceDirectory(target.parent());
            DurableCrashHooks.reach("v41-backup-before-future-completion-v1");
            return new DurableBackupResult(target.target(),
                    DurableBackupFormat.V1_0, contentIdentity, history,
                    sequence, 3, totalBytes);
        } catch (DurableOperationException exception) {
            primary = exception;
            throw exception;
        } catch (AtomicMoveNotSupportedException exception) {
            DurableOperationException wrapped = failure(
                    DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                    sequence, exception);
            primary = wrapped;
            throw wrapped;
        } catch (FileAlreadyExistsException exception) {
            DurableOperationException wrapped = failure(
                    DurableOperationException.Reason.TARGET_EXISTS,
                    sequence, exception);
            primary = wrapped;
            throw wrapped;
        } catch (ArithmeticException exception) {
            DurableOperationException wrapped = failure(
                    DurableOperationException.Reason.CAPACITY_EXCEEDED,
                    sequence, exception);
            primary = wrapped;
            throw wrapped;
        } catch (IOException exception) {
            DurableOperationException wrapped = failure(
                    DurableOperationException.Reason.IO_FAILURE,
                    sequence, exception);
            primary = wrapped;
            throw wrapped;
        } finally {
            closeMarker(markerLock, markerChannel, primary);
            if (!finalPublished) {
                cleanupCreated(staging, marker, stagingCreated, markerCreated,
                        primary);
            }
        }
    }

    private static Payload copyPayload(
            Path source,
            Path destination,
            String name,
            String partialBarrier,
            String forcedBarrier
    ) throws IOException {
        BasicFileAttributes before = attributes(source);
        MessageDigest digest = sha256();
        long copied = 0;
        try (FileChannel input = FileChannel.open(source, StandardOpenOption.READ);
                FileChannel output = FileChannel.open(destination,
                        StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            ByteBuffer buffer = ByteBuffer.allocate(COPY_BUFFER_BYTES);
            boolean first = true;
            while (input.read(buffer) >= 0) {
                if (buffer.position() == 0) {
                    break;
                }
                buffer.flip();
                digest.update(buffer.asReadOnlyBuffer());
                copied = Math.addExact(copied, buffer.remaining());
                while (buffer.hasRemaining()) {
                    if (DurableIoFaults.write(output, buffer) <= 0) {
                        throw new IOException("backup payload write made no progress");
                    }
                    if (first) {
                        first = false;
                        DurableCrashHooks.reach(partialBarrier);
                    }
                }
                buffer.clear();
            }
            DurableIoFaults.fail("v41-backup-before-payload-force");
            output.force(true);
        }
        DurableCrashHooks.reach(forcedBarrier);
        BasicFileAttributes after = attributes(source);
        if (copied != before.size() || !sameFile(before, after)) {
            throw failure(DurableOperationException.Reason.SOURCE_INVALID,
                    null, null);
        }
        return new Payload(name, copied, digest.digest());
    }

    private static void requireValidBundle(Path directory, long sequence) {
        DurableVerificationReport report = DurableStorageOperations.verifyBackup(
                directory);
        if (report.status() != DurableVerificationStatus.VALID
                || report.sequence().isEmpty()
                || report.sequence().getAsLong() != sequence) {
            throw failure(DurableOperationException.Reason.BACKUP_INVALID,
                    sequence, null);
        }
    }

    private static byte[] contentDigest(
            UUID history,
            long sequence,
            DurableStorageConfig<?, ?> config,
            String codecIdentity,
            int codecVersion,
            List<Payload> payloads
    ) {
        MessageDigest digest = sha256();
        digest.update(CONTENT_DOMAIN);
        updateString(digest, BACKUP_FAMILY);
        updateShort(digest, FORMAT_MAJOR);
        updateShort(digest, FORMAT_MINOR);
        updateString(digest, SOURCE_FAMILY);
        updateShort(digest, FORMAT_MAJOR);
        updateShort(digest, FORMAT_MINOR);
        updateLong(digest, history.getMostSignificantBits());
        updateLong(digest, history.getLeastSignificantBits());
        updateLong(digest, sequence);
        updateString(digest, config.storageIdentity());
        updateString(digest, config.schemaIdentity());
        updateString(digest, codecIdentity);
        updateInt(digest, codecVersion);
        updateInt(digest, payloads.size());
        payloads.stream().sorted(Comparator.comparing(Payload::name)).forEach(payload -> {
            updateString(digest, payload.name());
            updateLong(digest, payload.size());
            digest.update(payload.sha256());
        });
        return digest.digest();
    }

    private static byte[] encodeManifest(
            UUID history,
            long sequence,
            DurableStorageConfig<?, ?> config,
            String codecIdentity,
            int codecVersion,
            List<Payload> payloads,
            byte[] contentDigest,
            long createdEpochMillis,
            String requestId
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        CRC32C crc = new CRC32C();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(BACKUP_MAGIC);
            output.writeShort(FORMAT_MAJOR);
            output.writeShort(FORMAT_MINOR);
            writeString(output, BACKUP_FAMILY);
            writeString(output, SOURCE_FAMILY);
            output.writeShort(FORMAT_MAJOR);
            output.writeShort(FORMAT_MINOR);
            output.writeLong(history.getMostSignificantBits());
            output.writeLong(history.getLeastSignificantBits());
            output.writeLong(sequence);
            writeString(output, config.storageIdentity());
            writeString(output, config.schemaIdentity());
            writeString(output, codecIdentity);
            output.writeInt(codecVersion);
            output.writeInt(payloads.size());
            for (Payload payload : payloads) {
                writeString(output, payload.name());
                output.writeLong(payload.size());
                output.write(payload.sha256());
            }
            output.write(contentDigest);
            output.writeLong(createdEpochMillis);
            writeString(output, requestId);
            output.flush();
            crc.update(bytes.toByteArray());
            output.writeInt((int) crc.getValue());
        }
        return bytes.toByteArray();
    }

    private static byte[] encodeOperationMarker(
            UUID operationId,
            String stagingName,
            String targetName
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        CRC32C crc = new CRC32C();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(OPERATION_MAGIC);
            output.writeShort(FORMAT_MAJOR);
            output.writeShort(FORMAT_MINOR);
            output.writeByte(BACKUP_OPERATION);
            output.writeLong(operationId.getMostSignificantBits());
            output.writeLong(operationId.getLeastSignificantBits());
            writeString(output, stagingName);
            writeString(output, targetName);
            output.flush();
            crc.update(bytes.toByteArray());
            output.writeInt((int) crc.getValue());
        }
        return bytes.toByteArray();
    }

    private static void requireSourceMember(Path source) throws IOException {
        BasicFileAttributes attributes = attributes(source);
        if (!attributes.isRegularFile() || attributes.isSymbolicLink()
                || hardLinkCount(source) > 1) {
            throw failure(DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                    null, null);
        }
    }

    private static BasicFileAttributes attributes(Path path) throws IOException {
        return Files.readAttributes(path, BasicFileAttributes.class,
                LinkOption.NOFOLLOW_LINKS);
    }

    private static boolean sameFile(
            BasicFileAttributes left,
            BasicFileAttributes right
    ) {
        return left.isRegularFile() == right.isRegularFile()
                && left.isSymbolicLink() == right.isSymbolicLink()
                && left.size() == right.size()
                && left.lastModifiedTime().equals(right.lastModifiedTime())
                && Objects.equals(left.fileKey(), right.fileKey());
    }

    private static int hardLinkCount(Path path) {
        try {
            Object value = Files.getAttribute(path, "unix:nlink",
                    LinkOption.NOFOLLOW_LINKS);
            return value instanceof Number number ? number.intValue() : 1;
        } catch (IOException | RuntimeException unsupported) {
            return 1;
        }
    }

    private static FileLock acquireMarkerLock(
            FileChannel channel,
            long sequence
    ) throws IOException {
        try {
            FileLock lock = channel.tryLock();
            if (lock == null) {
                throw failure(DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                        sequence, null);
            }
            return lock;
        } catch (OverlappingFileLockException exception) {
            throw failure(DurableOperationException.Reason.OPERATION_IN_PROGRESS,
                    sequence, exception);
        }
    }

    private static void validateFileSystem(Path directory) throws IOException {
        FileStore store = Files.getFileStore(directory);
        String type = store.type().toLowerCase(Locale.ROOT);
        for (String marker : UNSUPPORTED_FILE_SYSTEM_MARKERS) {
            if (type.contains(marker)) {
                throw failure(DurableOperationException.Reason.UNSUPPORTED_FILESYSTEM,
                        null, null);
            }
        }
    }

    private static void moveAtomic(Path source, Path destination) throws IOException {
        Files.move(source, destination, StandardCopyOption.ATOMIC_MOVE);
    }

    private static void forceDirectory(Path directory) throws IOException {
        try (FileChannel channel = FileChannel.open(directory, StandardOpenOption.READ)) {
            channel.force(true);
        }
    }

    private static void writeFully(FileChannel channel, ByteBuffer bytes)
            throws IOException {
        while (bytes.hasRemaining()) {
            if (DurableIoFaults.write(channel, bytes) <= 0) {
                throw new IOException("backup write made no progress");
            }
        }
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        output.writeInt(encoded.length);
        output.write(encoded);
    }

    private static MessageDigest sha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private static void updateString(MessageDigest digest, String value) {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        updateInt(digest, encoded.length);
        digest.update(encoded);
    }

    private static void updateShort(MessageDigest digest, short value) {
        digest.update(ByteBuffer.allocate(Short.BYTES).order(ByteOrder.BIG_ENDIAN)
                .putShort(value).array());
    }

    private static void updateInt(MessageDigest digest, int value) {
        digest.update(ByteBuffer.allocate(Integer.BYTES).order(ByteOrder.BIG_ENDIAN)
                .putInt(value).array());
    }

    private static void updateLong(MessageDigest digest, long value) {
        digest.update(ByteBuffer.allocate(Long.BYTES).order(ByteOrder.BIG_ENDIAN)
                .putLong(value).array());
    }

    private static DurableOperationException failure(
            DurableOperationException.Reason reason,
            Long sequence,
            Throwable cause
    ) {
        return new DurableOperationException(reason,
                sequence == null ? OptionalLong.empty() : OptionalLong.of(sequence),
                cause);
    }

    private static void closeMarker(
            FileLock lock,
            FileChannel channel,
            Throwable primary
    ) {
        if (lock != null) {
            try {
                lock.close();
            } catch (IOException exception) {
                suppress(primary, exception);
            }
        }
        if (channel != null) {
            try {
                channel.close();
            } catch (IOException exception) {
                suppress(primary, exception);
            }
        }
    }

    private static void cleanupCreated(
            Path staging,
            Path marker,
            boolean stagingCreated,
            boolean markerCreated,
            Throwable primary
    ) {
        try {
            if (stagingCreated
                    && Files.isDirectory(staging, LinkOption.NOFOLLOW_LINKS)
                    && !Files.isSymbolicLink(staging)) {
                for (String name : OWNED_STAGING_MEMBERS) {
                    Path member = staging.resolve(name);
                    if (!Files.isDirectory(member, LinkOption.NOFOLLOW_LINKS)) {
                        Files.deleteIfExists(member);
                    }
                }
                Files.deleteIfExists(staging);
            }
            if (markerCreated) {
                Files.deleteIfExists(marker);
            }
            if (stagingCreated || markerCreated) {
                forceDirectory(marker.getParent());
            }
        } catch (IOException | RuntimeException exception) {
            suppress(primary, exception);
        }
    }

    private static void suppress(Throwable primary, Throwable later) {
        if (primary != null) {
            primary.addSuppressed(later);
        }
    }

    record Target(Path parent, Path target) {
        Target {
            Objects.requireNonNull(parent, "parent");
            Objects.requireNonNull(target, "target");
        }
    }

    private record Payload(String name, long size, byte[] sha256) {
        private Payload {
            Objects.requireNonNull(name, "name");
            sha256 = sha256.clone();
            if (!PAYLOAD_ORDER.contains(name) || size <= 0 || sha256.length != 32) {
                throw new IllegalArgumentException("invalid backup payload descriptor");
            }
        }

        @Override
        public byte[] sha256() {
            return sha256.clone();
        }
    }
}
