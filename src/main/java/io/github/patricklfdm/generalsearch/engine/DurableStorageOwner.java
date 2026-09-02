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
import java.nio.file.FileStore;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;

final class DurableStorageOwner implements AutoCloseable {
    static final String LOCK_FILE = "gse.lock";
    static final String METADATA_FILE = "gse-metadata";
    static final String METADATA_STAGING_FILE = "gse-metadata.staging";
    static final String WAL_FILE = "gse-wal-00000000000000000001.log";

    private static final long METADATA_MAGIC = 0x4753454d45544131L; // GSEMETA1
    private static final short FORMAT_MAJOR = 1;
    private static final short FORMAT_MINOR = 0;
    private static final Set<String> UNSUPPORTED_FILE_SYSTEM_MARKERS = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");

    private final Path directory;
    private final FileChannel lockChannel;
    private final FileLock lock;
    private final DurableWal wal;
    private final long metadataBytes;
    private boolean closed;

    private DurableStorageOwner(
            Path directory,
            FileChannel lockChannel,
            FileLock lock,
            DurableWal wal,
            long metadataBytes
    ) {
        this.directory = directory;
        this.lockChannel = lockChannel;
        this.lock = lock;
        this.wal = wal;
        this.metadataBytes = metadataBytes;
    }

    static <K, T> DurableStorageOwner createFresh(
            DurableStorageConfig<K, T> config,
            String codecId,
            int codecVersion,
            List<DurableIndexDescriptor> startupIndexes
    ) {
        Path configured = config.directory().toAbsolutePath().normalize();
        if (Files.isSymbolicLink(config.directory())
                || Files.isSymbolicLink(configured)) {
            throw failure(
                    DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                    "durable storage directory must not be a symbolic link",
                    null);
        }
        try {
            Files.createDirectories(configured);
            Path directory = configured.toRealPath();
            validateFileSystem(directory);
            Path lockPath = directory.resolve(LOCK_FILE);
            if (Files.isSymbolicLink(lockPath)) {
                throw failure(
                        DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                        "durable storage lock must not be a symbolic link",
                        null);
            }
            FileChannel lockChannel = FileChannel.open(
                    lockPath,
                    StandardOpenOption.CREATE,
                    StandardOpenOption.READ,
                    StandardOpenOption.WRITE);
            FileLock lock;
            try {
                lock = acquire(lockChannel);
            } catch (RuntimeException | IOException failure) {
                lockChannel.close();
                throw failure;
            }
            boolean success = false;
            DurableWal wal = null;
            Throwable primary = null;
            try {
                validateFreshDirectory(directory);
                UUID historyId = UUID.randomUUID();
                byte[] metadata = encodeMetadata(
                        config, codecId, codecVersion, startupIndexes, historyId);
                long initialBytes = metadata.length
                        + (long) DurableWal.GENERATION_HEADER_BYTES;
                if (initialBytes > config.maxRetainedBytes()) {
                    throw failure(
                            DurabilityException.Reason.CAPACITY_EXCEEDED,
                            "fresh durable metadata exceeds the retained-byte limit",
                            null);
                }
                writeMetadata(directory, metadata);
                wal = DurableWal.create(
                        directory.resolve(WAL_FILE), historyId);
                forceDirectory(directory);
                success = true;
                return new DurableStorageOwner(
                        directory,
                        lockChannel,
                        lock,
                        wal,
                        metadata.length);
            } catch (RuntimeException | IOException | Error failure) {
                primary = failure;
                throw failure;
            } finally {
                if (!success) {
                    closeAfterFailedInitialization(
                            wal, lock, lockChannel, primary);
                }
            }
        } catch (DurabilityException failure) {
            throw failure;
        } catch (IOException failure) {
            throw failure(
                    DurabilityException.Reason.STORAGE_ACCESS,
                    "durable storage initialization failed",
                    failure);
        }
    }

    DurableWal wal() {
        return wal;
    }

    long retainedBytes() {
        return metadataBytes + wal.position();
    }

    Path directory() {
        return directory;
    }

    private static FileLock acquire(FileChannel channel) throws IOException {
        try {
            FileLock acquired = channel.tryLock();
            if (acquired == null) {
                throw failure(
                        DurabilityException.Reason.STORAGE_IN_USE,
                        "durable storage directory is already owned",
                        null);
            }
            return acquired;
        } catch (OverlappingFileLockException failure) {
            throw failure(
                    DurabilityException.Reason.STORAGE_IN_USE,
                    "durable storage directory is already owned",
                    failure);
        }
    }

    private static void validateFreshDirectory(Path directory) throws IOException {
        try (var entries = Files.list(directory)) {
            List<String> names = entries
                    .map(path -> path.getFileName().toString())
                    .filter(name -> !name.equals(LOCK_FILE))
                    .sorted()
                    .toList();
            if (names.isEmpty()) {
                return;
            }
            if (names.contains(METADATA_FILE) || names.contains(WAL_FILE)) {
                throw failure(
                        DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                        "opening initialized durable storage begins in V4 Phase 3",
                        null);
            }
            throw failure(
                    DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                    "durable target directory is not empty",
                    null);
        }
    }

    private static void validateFileSystem(Path directory) throws IOException {
        FileStore store = Files.getFileStore(directory);
        String type = store.type().toLowerCase(Locale.ROOT);
        for (String marker : UNSUPPORTED_FILE_SYSTEM_MARKERS) {
            if (type.contains(marker)) {
                throw failure(
                        DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                        "unsupported durable filesystem type: " + type,
                        null);
            }
        }
    }

    private static <K, T> byte[] encodeMetadata(
            DurableStorageConfig<K, T> config,
            String codecId,
            int codecVersion,
            List<DurableIndexDescriptor> indexes,
            UUID historyId
    ) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (DataOutputStream output = new DataOutputStream(bytes)) {
            output.writeLong(METADATA_MAGIC);
            output.writeShort(FORMAT_MAJOR);
            output.writeShort(FORMAT_MINOR);
            output.writeLong(historyId.getMostSignificantBits());
            output.writeLong(historyId.getLeastSignificantBits());
            writeString(output, "gse-durable");
            writeString(output, config.storageIdentity());
            writeString(output, config.schemaIdentity());
            writeString(output, codecId);
            output.writeInt(codecVersion);
            output.writeInt(config.maxEncodedKeyBytes());
            output.writeInt(config.maxEncodedDocumentBytes());
            output.writeInt(config.maxBulkElements());
            output.writeInt(config.maxDocuments());
            output.writeLong(config.checkpointWalBytes());
            output.writeLong(config.maxRetainedBytes());
            output.writeInt(indexes.size());
            for (DurableIndexDescriptor index : indexes) {
                output.writeByte(index.kind());
                writeString(output, index.fieldName());
                writeString(output, index.analyzerId());
            }
        }
        byte[] content = bytes.toByteArray();
        CRC32C checksum = new CRC32C();
        checksum.update(content, 0, content.length);
        ByteBuffer complete = ByteBuffer.allocate(content.length + Integer.BYTES)
                .order(ByteOrder.BIG_ENDIAN)
                .put(content)
                .putInt((int) checksum.getValue());
        return complete.array();
    }

    private static void writeString(DataOutputStream output, String value)
            throws IOException {
        byte[] encoded = value.getBytes(StandardCharsets.UTF_8);
        output.writeInt(encoded.length);
        output.write(encoded);
    }

    private static void writeMetadata(Path directory, byte[] metadata)
            throws IOException {
        Path staging = directory.resolve(METADATA_STAGING_FILE);
        Path authoritative = directory.resolve(METADATA_FILE);
        try (FileChannel channel = FileChannel.open(
                staging,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE)) {
            ByteBuffer buffer = ByteBuffer.wrap(metadata);
            while (buffer.hasRemaining()) {
                int written = channel.write(buffer);
                if (written <= 0) {
                    throw new IOException("metadata write made no progress");
                }
            }
            channel.force(true);
        }
        try {
            Files.move(
                    staging,
                    authoritative,
                    StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException failure) {
            throw failure(
                    DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                    "durable storage requires same-filesystem atomic rename",
                    failure);
        }
        forceDirectory(directory);
    }

    private static void forceDirectory(Path directory) throws IOException {
        try (FileChannel channel = FileChannel.open(directory, StandardOpenOption.READ)) {
            channel.force(true);
        }
    }

    private static DurabilityException failure(
            DurabilityException.Reason reason,
            String message,
            Throwable cause
    ) {
        return cause == null
                ? new DurabilityException(reason, message)
                : new DurabilityException(reason, message, cause);
    }

    private static void closeAfterFailedInitialization(
            DurableWal wal,
            FileLock lock,
            FileChannel lockChannel,
            Throwable primary
    ) {
        try {
            if (wal != null) {
                wal.close();
            }
        } catch (IOException cleanupFailure) {
            addSuppressed(primary, cleanupFailure);
        }
        try {
            lock.release();
        } catch (IOException cleanupFailure) {
            addSuppressed(primary, cleanupFailure);
        }
        try {
            lockChannel.close();
        } catch (IOException cleanupFailure) {
            addSuppressed(primary, cleanupFailure);
        }
    }

    private static void addSuppressed(Throwable primary, Throwable cleanupFailure) {
        if (primary != null) {
            primary.addSuppressed(cleanupFailure);
        }
    }

    @Override
    public void close() {
        if (closed) {
            return;
        }
        closed = true;
        IOException primary = null;
        try {
            wal.close();
        } catch (IOException failure) {
            primary = failure;
        }
        try {
            lock.release();
        } catch (IOException failure) {
            if (primary == null) {
                primary = failure;
            } else {
                primary.addSuppressed(failure);
            }
        }
        try {
            lockChannel.close();
        } catch (IOException failure) {
            if (primary == null) {
                primary = failure;
            } else {
                primary.addSuppressed(failure);
            }
        }
        if (primary != null) {
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "durable storage close failed",
                    primary);
        }
    }
}
