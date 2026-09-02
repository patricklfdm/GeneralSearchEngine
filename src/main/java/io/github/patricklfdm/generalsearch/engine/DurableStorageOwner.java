package io.github.patricklfdm.generalsearch.engine;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.BufferUnderflowException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.FileStore;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
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
    private static final String FORMAT_FAMILY = "gse-durable";
    private static final int MAX_METADATA_BYTES = 64 * 1024 * 1024;
    private static final int MAX_STARTUP_INDEXES = 100_000;
    private static final Set<String> UNSUPPORTED_FILE_SYSTEM_MARKERS = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");
    private static final Set<String> INITIALIZED_NAMES = Set.of(
            METADATA_FILE, WAL_FILE);

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

    static <K, T> OpenResult open(
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
                Set<String> members = directoryMembers(directory);
                if (members.isEmpty()) {
                    UUID historyId = UUID.randomUUID();
                    byte[] metadata = encodeMetadata(
                            config,
                            codecId,
                            codecVersion,
                            startupIndexes,
                            historyId);
                    long initialBytes = metadata.length
                            + (long) DurableWal.GENERATION_HEADER_BYTES;
                    if (initialBytes > config.maxRetainedBytes()) {
                        throw failure(
                                DurabilityException.Reason.CAPACITY_EXCEEDED,
                                "fresh durable metadata exceeds the retained-byte limit",
                                null);
                    }
                    writeMetadata(directory, metadata);
                    wal = DurableWal.create(directory.resolve(WAL_FILE), historyId);
                    forceDirectory(directory);
                    DurableStorageOwner owner = new DurableStorageOwner(
                            directory,
                            lockChannel,
                            lock,
                            wal,
                            metadata.length);
                    success = true;
                    return new OpenResult(owner, 0, true, 0);
                }

                validateInitializedMembers(directory, members);
                Path metadataPath = directory.resolve(METADATA_FILE);
                Metadata metadata = readMetadata(metadataPath);
                validateMetadata(
                        metadata,
                        config,
                        codecId,
                        codecVersion,
                        startupIndexes);
                long metadataSize = Files.size(metadataPath);
                long walSize = Files.size(directory.resolve(WAL_FILE));
                if (Math.addExact(metadataSize, walSize)
                        > config.maxRetainedBytes()) {
                    throw failure(
                            DurabilityException.Reason.CAPACITY_EXCEEDED,
                            "initialized durable storage exceeds retained-byte limit",
                            null);
                }
                DurableWal.OpenResult openedWal = DurableWal.open(
                        directory.resolve(WAL_FILE), metadata.historyId());
                wal = openedWal.wal();
                long retainedBytes = Math.addExact(
                        metadataSize, wal.position());
                if (retainedBytes > config.maxRetainedBytes()) {
                    throw failure(
                            DurabilityException.Reason.CAPACITY_EXCEEDED,
                            "initialized durable storage exceeds retained-byte limit",
                            null);
                }
                DurableStorageOwner owner = new DurableStorageOwner(
                        directory,
                        lockChannel,
                        lock,
                        wal,
                        metadataSize);
                success = true;
                return new OpenResult(
                        owner,
                        openedWal.records(),
                        false,
                        openedWal.truncatedBytes());
            } catch (RuntimeException | IOException | Error failure) {
                primary = failure;
                throw failure;
            } finally {
                if (!success) {
                    closeAfterFailedInitialization(wal, lock, lockChannel, primary);
                }
            }
        } catch (DurabilityException failure) {
            throw failure;
        } catch (ArithmeticException failure) {
            throw failure(
                    DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                    "durable storage byte count overflowed",
                    failure);
        } catch (IOException failure) {
            throw failure(
                    DurabilityException.Reason.STORAGE_ACCESS,
                    "durable storage open failed",
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

    private static Set<String> directoryMembers(Path directory) throws IOException {
        try (var entries = Files.list(directory)) {
            return entries
                    .map(path -> path.getFileName().toString())
                    .filter(name -> !name.equals(LOCK_FILE))
                    .collect(java.util.stream.Collectors.toUnmodifiableSet());
        }
    }

    private static void validateInitializedMembers(
            Path directory,
            Set<String> members
    ) {
        if (!members.equals(INITIALIZED_NAMES)) {
            throw failure(
                    DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                    "initialized durable directory has missing or unknown members",
                    null);
        }
        for (String name : INITIALIZED_NAMES) {
            Path path = directory.resolve(name);
            if (Files.isSymbolicLink(path) || !Files.isRegularFile(path)) {
                throw failure(
                        DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                        "durable storage members must be regular non-symbolic files",
                        null);
            }
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
            writeString(output, FORMAT_FAMILY);
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
        return ByteBuffer.allocate(content.length + Integer.BYTES)
                .order(ByteOrder.BIG_ENDIAN)
                .put(content)
                .putInt((int) checksum.getValue())
                .array();
    }

    private static Metadata readMetadata(Path path) throws IOException {
        long size = Files.size(path);
        if (size < 64 || size > MAX_METADATA_BYTES) {
            throw incompatible("durable metadata has an invalid size", null);
        }
        byte[] encoded = Files.readAllBytes(path);
        if (encoded.length != size) {
            throw incompatible("durable metadata changed while being read", null);
        }
        CRC32C checksum = new CRC32C();
        checksum.update(encoded, 0, encoded.length - Integer.BYTES);
        int storedChecksum = ByteBuffer.wrap(
                encoded,
                encoded.length - Integer.BYTES,
                Integer.BYTES).order(ByteOrder.BIG_ENDIAN).getInt();
        if ((int) checksum.getValue() != storedChecksum) {
            throw incompatible("durable metadata checksum mismatch", null);
        }

        try {
            MetadataReader reader = new MetadataReader(
                    ByteBuffer.wrap(encoded, 0, encoded.length - Integer.BYTES)
                            .order(ByteOrder.BIG_ENDIAN));
            long magic = reader.readLong("metadata magic");
            short major = reader.readShort("metadata major");
            short minor = reader.readShort("metadata minor");
            UUID historyId = new UUID(
                    reader.readLong("history most"),
                    reader.readLong("history least"));
            String family = reader.readString(128, false, "format family");
            String storageIdentity = reader.readString(
                    128, false, "storage identity");
            String schemaIdentity = reader.readString(
                    128, false, "schema identity");
            String codecId = reader.readString(128, false, "codec identity");
            int codecVersion = reader.readInt("codec version");
            int maxKeyBytes = reader.readInt("maximum key bytes");
            int maxDocumentBytes = reader.readInt("maximum document bytes");
            int maxBulkElements = reader.readInt("maximum bulk elements");
            int maxDocuments = reader.readInt("maximum documents");
            long checkpointWalBytes = reader.readLong("checkpoint WAL bytes");
            long maxRetainedBytes = reader.readLong("maximum retained bytes");
            int indexCount = reader.readInt("startup index count");
            if (indexCount < 0 || indexCount > MAX_STARTUP_INDEXES) {
                throw incompatible("metadata startup index count is invalid", null);
            }
            List<DurableIndexDescriptor> indexes = new java.util.ArrayList<>(
                    indexCount);
            Set<DurableIndexDescriptor> distinct = new HashSet<>();
            for (int index = 0; index < indexCount; index++) {
                DurableIndexDescriptor descriptor = new DurableIndexDescriptor(
                        reader.readByte("index kind"),
                        reader.readString(1024, false, "index field"),
                        reader.readString(128, true, "index analyzer"));
                if (!distinct.add(descriptor)) {
                    throw incompatible("metadata contains a duplicate index", null);
                }
                indexes.add(descriptor);
            }
            reader.requireExhausted();
            return new Metadata(
                    magic,
                    major,
                    minor,
                    historyId,
                    family,
                    storageIdentity,
                    schemaIdentity,
                    codecId,
                    codecVersion,
                    maxKeyBytes,
                    maxDocumentBytes,
                    maxBulkElements,
                    maxDocuments,
                    checkpointWalBytes,
                    maxRetainedBytes,
                    indexes);
        } catch (DurabilityException failure) {
            throw failure;
        } catch (BufferUnderflowException | IllegalArgumentException failure) {
            throw incompatible("durable metadata structure is invalid", failure);
        }
    }

    private static <K, T> void validateMetadata(
            Metadata metadata,
            DurableStorageConfig<K, T> config,
            String codecId,
            int codecVersion,
            List<DurableIndexDescriptor> startupIndexes
    ) {
        if (metadata.magic() != METADATA_MAGIC
                || metadata.major() != FORMAT_MAJOR
                || metadata.minor() != FORMAT_MINOR
                || !metadata.family().equals(FORMAT_FAMILY)
                || metadata.historyId().equals(new UUID(0L, 0L))) {
            throw incompatible("durable metadata format identity is incompatible", null);
        }
        if (!metadata.storageIdentity().equals(config.storageIdentity())
                || !metadata.schemaIdentity().equals(config.schemaIdentity())
                || !metadata.codecId().equals(codecId)
                || metadata.codecVersion() != codecVersion) {
            throw incompatible("durable storage, schema, or codec identity changed", null);
        }
        if (metadata.maxKeyBytes() != config.maxEncodedKeyBytes()
                || metadata.maxDocumentBytes()
                        != config.maxEncodedDocumentBytes()
                || metadata.maxBulkElements() != config.maxBulkElements()
                || metadata.maxDocuments() != config.maxDocuments()
                || metadata.checkpointWalBytes() != config.checkpointWalBytes()
                || metadata.maxRetainedBytes() != config.maxRetainedBytes()) {
            throw incompatible("durable storage safety bounds changed", null);
        }
        if (!metadata.indexes().equals(startupIndexes)) {
            throw incompatible("durable startup index configuration changed", null);
        }
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
            Files.move(staging, authoritative, StandardCopyOption.ATOMIC_MOVE);
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

    private static DurabilityException incompatible(
            String message,
            Throwable cause
    ) {
        return failure(
                DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                message,
                cause);
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

    record OpenResult(
            DurableStorageOwner owner,
            long records,
            boolean fresh,
            long truncatedBytes
    ) {
        OpenResult {
            Objects.requireNonNull(owner, "owner");
            if ((fresh && (records != 0 || truncatedBytes != 0))
                    || records < 0 || truncatedBytes < 0) {
                throw new IllegalArgumentException("invalid durable open result");
            }
        }
    }

    private record Metadata(
            long magic,
            short major,
            short minor,
            UUID historyId,
            String family,
            String storageIdentity,
            String schemaIdentity,
            String codecId,
            int codecVersion,
            int maxKeyBytes,
            int maxDocumentBytes,
            int maxBulkElements,
            int maxDocuments,
            long checkpointWalBytes,
            long maxRetainedBytes,
            List<DurableIndexDescriptor> indexes
    ) {
        Metadata {
            Objects.requireNonNull(historyId, "historyId");
            indexes = List.copyOf(indexes);
        }
    }

    private static final class MetadataReader {
        private final ByteBuffer bytes;

        private MetadataReader(ByteBuffer bytes) {
            this.bytes = bytes;
        }

        private byte readByte(String name) {
            requireRemaining(Byte.BYTES, name);
            return bytes.get();
        }

        private short readShort(String name) {
            requireRemaining(Short.BYTES, name);
            return bytes.getShort();
        }

        private int readInt(String name) {
            requireRemaining(Integer.BYTES, name);
            return bytes.getInt();
        }

        private long readLong(String name) {
            requireRemaining(Long.BYTES, name);
            return bytes.getLong();
        }

        private String readString(int maximum, boolean allowEmpty, String name) {
            int length = readInt(name + " length");
            if (length < 0 || length > maximum || (!allowEmpty && length == 0)) {
                throw new IllegalArgumentException(name + " has invalid length");
            }
            requireRemaining(length, name);
            ByteBuffer encoded = bytes.slice();
            encoded.limit(length);
            bytes.position(bytes.position() + length);
            try {
                return StandardCharsets.UTF_8.newDecoder()
                        .onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT)
                        .decode(encoded)
                        .toString();
            } catch (CharacterCodingException failure) {
                throw new IllegalArgumentException(name + " is not strict UTF-8", failure);
            }
        }

        private void requireExhausted() {
            if (bytes.hasRemaining()) {
                throw new IllegalArgumentException("metadata has trailing bytes");
            }
        }

        private void requireRemaining(int length, String name) {
            if (length < 0 || length > bytes.remaining()) {
                throw new IllegalArgumentException(name + " is truncated");
            }
        }
    }
}
