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
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.HashSet;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.CRC32C;
import io.github.patricklfdm.generalsearch.durability.DurableStorageConfig;
import io.github.patricklfdm.generalsearch.durability.DurabilityException;

final class DurableStorageOwner implements AutoCloseable {
    static final String LOCK_FILE = "gse.lock";
    static final String METADATA_FILE = "gse-metadata";
    static final String METADATA_STAGING_FILE = "gse-metadata.staging";
    static final String WAL_FILE = "gse-wal-00000000000000000001.log";
    private static final Pattern WAL_NAME = Pattern.compile(
            "gse-wal-([0-9]{20})\\.log");

    private static final long METADATA_MAGIC = 0x4753454d45544131L; // GSEMETA1
    private static final short FORMAT_MAJOR = 1;
    private static final short FORMAT_MINOR = 0;
    private static final String FORMAT_FAMILY = "gse-durable";
    private static final int MAX_METADATA_BYTES = 64 * 1024 * 1024;
    private static final int MAX_STARTUP_INDEXES = 100_000;
    private static final Set<String> UNSUPPORTED_FILE_SYSTEM_MARKERS = Set.of(
            "nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p");
    private final Path directory;
    private final FileChannel lockChannel;
    private final FileLock lock;
    private final UUID historyId;
    private final long metadataBytes;
    private volatile DurableWal wal;
    private List<DurableWal> replayWals;
    private volatile DurableCheckpoint.Manifest manifest;
    private boolean closed;

    private DurableStorageOwner(
            Path directory,
            FileChannel lockChannel,
            FileLock lock,
            UUID historyId,
            DurableWal wal,
            long metadataBytes,
            List<DurableWal> replayWals,
            DurableCheckpoint.Manifest manifest
    ) {
        this.directory = directory;
        this.lockChannel = lockChannel;
        this.lock = lock;
        this.historyId = Objects.requireNonNull(historyId, "historyId");
        this.wal = wal;
        this.metadataBytes = metadataBytes;
        this.replayWals = List.copyOf(replayWals);
        this.manifest = manifest;
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
            List<DurableWal> openedWals = new ArrayList<>();
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
                    wal = DurableWal.create(
                            directory.resolve(WAL_FILE),
                            historyId,
                            DurableWal.INITIAL_GENERATION,
                            1L);
                    forceDirectory(directory);
                    DurableStorageOwner owner = new DurableStorageOwner(
                            directory,
                            lockChannel,
                            lock,
                            historyId,
                            wal,
                            metadata.length,
                            List.of(wal),
                            null);
                    success = true;
                    return new OpenResult(
                            owner, List.of(wal), null, true, 0);
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
                long retainedSize = retainedBytes(directory);
                if (retainedSize > config.maxRetainedBytes()) {
                    throw failure(
                            DurabilityException.Reason.CAPACITY_EXCEEDED,
                            "initialized durable storage exceeds retained-byte limit",
                            null);
                }
                DurableCheckpoint.Manifest checkpointManifest =
                        members.contains(DurableCheckpoint.MANIFEST_FILE)
                                ? DurableCheckpoint.readManifest(
                                        directory.resolve(
                                                DurableCheckpoint.MANIFEST_FILE),
                                        metadata.historyId())
                                : null;
                if (checkpointManifest != null
                        && !members.contains(
                                checkpointManifest.checkpointFile())) {
                    throw new DurabilityException(
                            DurabilityException.Reason.CORRUPT_CHECKPOINT,
                            "authoritative checkpoint data file is missing");
                }

                List<WalMember> walMembers = walMembers(directory, members);
                openedWals = new ArrayList<>(walMembers.size());
                long truncatedBytes = 0;
                long previousGeneration = 0;
                long expectedNextSequence = 0;
                boolean manifestGenerationFound = checkpointManifest == null;
                for (int index = 0; index < walMembers.size(); index++) {
                    WalMember member = walMembers.get(index);
                    DurableWal.Header header = DurableWal.inspectHeader(
                            member.path(), metadata.historyId());
                    if (header.generation() != member.generation()
                            || (previousGeneration != 0
                            && member.generation() != previousGeneration + 1)
                            || (previousGeneration == 0
                            && member.generation() == DurableWal.INITIAL_GENERATION
                            && header.firstSequence() != 1L)
                            || (expectedNextSequence != 0
                            && header.firstSequence() != expectedNextSequence)) {
                        throw new DurabilityException(
                                DurabilityException.Reason.CORRUPT_WAL,
                                "retained WAL generations are not contiguous");
                    }
                    if (checkpointManifest != null
                            && member.generation()
                            == checkpointManifest.walGeneration()) {
                        manifestGenerationFound = true;
                        if (header.firstSequence()
                                != checkpointManifest.walFirstSequence()) {
                            throw new DurabilityException(
                                    DurabilityException.Reason.CORRUPT_WAL,
                                    "manifest WAL boundary does not match generation");
                        }
                    }
                    DurableWal.OpenResult opened = DurableWal.open(
                            member.path(),
                            metadata.historyId(),
                            member.generation(),
                            header.firstSequence(),
                            index == walMembers.size() - 1);
                    openedWals.add(opened.wal());
                    truncatedBytes = Math.addExact(
                            truncatedBytes, opened.truncatedBytes());
                    previousGeneration = member.generation();
                    expectedNextSequence = Math.addExact(
                            opened.wal().lastSequence(), 1L);
                }
                if (!manifestGenerationFound
                        || (checkpointManifest != null
                        && walMembers.getFirst().generation()
                        > checkpointManifest.walGeneration())) {
                    throw new DurabilityException(
                            DurabilityException.Reason.CORRUPT_WAL,
                            "authoritative post-checkpoint WAL generation is missing");
                }
                wal = openedWals.getLast();
                DurableStorageOwner owner = new DurableStorageOwner(
                        directory,
                        lockChannel,
                        lock,
                        metadata.historyId(),
                        wal,
                        metadataSize,
                        openedWals,
                        checkpointManifest);
                success = true;
                return new OpenResult(
                        owner,
                        openedWals,
                        checkpointManifest,
                        false,
                        truncatedBytes);
            } catch (RuntimeException | IOException | Error failure) {
                primary = failure;
                throw failure;
            } finally {
                if (!success) {
                    for (DurableWal openedWal : openedWals) {
                        if (openedWal != wal) {
                            try {
                                openedWal.close();
                            } catch (IOException closeFailure) {
                                if (primary != null) {
                                    primary.addSuppressed(closeFailure);
                                }
                            }
                        }
                    }
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

    synchronized DurableWal wal() {
        return wal;
    }

    long retainedBytes() {
        try {
            return retainedBytes(directory);
        } catch (IOException | ArithmeticException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "durable retained-byte lookup failed",
                    failure);
        }
    }

    Path directory() {
        return directory;
    }

    UUID historyId() {
        return historyId;
    }

    DurableCheckpoint.Manifest manifest() {
        return manifest;
    }

    synchronized void finishRecovery() {
        for (DurableWal replay : replayWals) {
            if (replay != wal) {
                try {
                    replay.close();
                } catch (IOException failure) {
                    throw new DurabilityException(
                            DurabilityException.Reason.STORAGE_ACCESS,
                            "retained WAL close after recovery failed",
                            failure);
                }
            }
        }
        replayWals = List.of(wal);
    }

    synchronized GenerationCut cutGeneration(
            long nextFirstSequence,
            long maxRetainedBytes
    ) {
        if (closed) {
            throw new DurabilityException(
                    DurabilityException.Reason.CLOSED,
                    "durable storage is closed");
        }
        if (nextFirstSequence <= 0) {
            throw new DurabilityException(
                    DurabilityException.Reason.SEQUENCE_EXHAUSTED,
                    "checkpoint cannot open a post-cut WAL sequence");
        }
        if (maxRetainedBytes <= 0
                || retainedBytes() > maxRetainedBytes
                        - DurableWal.GENERATION_HEADER_BYTES) {
            throw new DurabilityException(
                    DurabilityException.Reason.CAPACITY_EXCEEDED,
                    "checkpoint WAL generation exceeds retained-byte limit");
        }
        DurableWal previous = wal;
        DurableWal next = null;
        try {
            previous.force();
            DurableCrashHooks.reach(
                    "v4-checkpoint-after-old-wal-force-v1");
            long nextGeneration = Math.incrementExact(previous.generation());
            Path nextPath = directory.resolve(walFile(nextGeneration));
            next = DurableWal.create(
                    nextPath, historyId, nextGeneration, nextFirstSequence);
            forceDirectory(directory);
            DurableCrashHooks.reach(
                    "v4-checkpoint-after-new-wal-header-force-v1");
            wal = next;
            replayWals = List.of(next);
            previous.close();
            return new GenerationCut(nextGeneration, nextFirstSequence);
        } catch (IOException | ArithmeticException failure) {
            if (next != null && next != wal) {
                try {
                    next.close();
                } catch (IOException closeFailure) {
                    failure.addSuppressed(closeFailure);
                }
            }
            throw new DurabilityException(
                    DurabilityException.Reason.IO_FAILURE,
                    "WAL generation cut failed",
                    failure);
        }
    }

    <K, T> CheckpointPublication publishCheckpoint(
            DurableCheckpoint.Capture<K, T> capture,
            DurableStorageConfig<K, T> config,
            io.github.patricklfdm.generalsearch.schema.SearchSchema<T, K> schema,
            GenerationCut cut
    ) {
        String checkpointFile = DurableCheckpoint.newCheckpointFile(
                capture.sequence());
        Path finalData = directory.resolve(checkpointFile);
        Path stagingData = directory.resolve(checkpointFile + ".staging");
        Path stagingManifest = directory.resolve(
                DurableCheckpoint.MANIFEST_STAGING_FILE);
        boolean manifestReplaced = false;
        try {
            deleteStaging(stagingManifest);
            int manifestReserve = DurableCheckpoint.encodeManifest(
                    new DurableCheckpoint.Manifest(
                            capture.sequence(),
                            checkpointFile,
                            56,
                            0,
                            cut.generation(),
                            cut.firstSequence()),
                    historyId).length;
            long available = Math.subtractExact(
                    Math.subtractExact(
                            config.maxRetainedBytes(), retainedBytes()),
                    manifestReserve);
            DurableCheckpoint.Written written = DurableCheckpoint.write(
                    stagingData,
                    capture,
                    config,
                    schema,
                    historyId,
                    available);
            DurableCheckpoint.Loaded<K, T> validated = DurableCheckpoint.read(
                    stagingData, config, schema, historyId, null);
            if (validated.sequence() != capture.sequence()
                    || validated.nextDocId() != capture.nextDocId()
                    || !validated.documentIds().equals(capture.documentIds())
                    || !validated.indexes().equals(capture.indexes())) {
                throw new DurabilityException(
                        DurabilityException.Reason.CORRUPT_CHECKPOINT,
                        "checkpoint staging validation does not match capture");
            }
            DurableIoFaults.fail("checkpoint-before-data-rename");
            moveAtomic(stagingData, finalData, false);
            forceDirectory(directory);
            DurableCrashHooks.reach(
                    "v4-checkpoint-after-data-publication-v1");

            DurableCheckpoint.Manifest nextManifest =
                    new DurableCheckpoint.Manifest(
                            capture.sequence(),
                            checkpointFile,
                            written.bytes(),
                            written.checksum(),
                            cut.generation(),
                            cut.firstSequence());
            byte[] manifestBytes = DurableCheckpoint.encodeManifest(
                    nextManifest, historyId);
            if (Math.addExact(retainedBytes(), manifestBytes.length)
                    > config.maxRetainedBytes()) {
                throw new DurabilityException(
                        DurabilityException.Reason.CAPACITY_EXCEEDED,
                        "checkpoint manifest exceeds retained-byte limit");
            }
            writeManifestStaging(stagingManifest, manifestBytes);
            DurableCrashHooks.reach(
                    "v4-checkpoint-after-manifest-force-v1");
            DurableIoFaults.fail("checkpoint-before-manifest-rename");
            moveAtomic(
                    stagingManifest,
                    directory.resolve(DurableCheckpoint.MANIFEST_FILE),
                    true);
            manifestReplaced = true;
            DurableCrashHooks.reach(
                    "v4-checkpoint-after-manifest-rename-v1");
            DurableIoFaults.fail("checkpoint-before-directory-force");
            forceDirectory(directory);
            DurableCrashHooks.reach(
                    "v4-checkpoint-after-directory-force-v1");
            manifest = nextManifest;

            DurableCrashHooks.reach(
                    "v4-checkpoint-before-wal-cleanup-v1");
            DurabilityException.Reason cleanupFailure = cleanupAfterPublication(
                    nextManifest);
            DurableCrashHooks.reach(
                    "v4-checkpoint-after-wal-cleanup-v1");
            return new CheckpointPublication(nextManifest, cleanupFailure);
        } catch (DurabilityException failure) {
            throw new CheckpointFailure(failure, manifestReplaced);
        } catch (IOException | ArithmeticException failure) {
            throw new CheckpointFailure(
                    new DurabilityException(
                            DurabilityException.Reason.IO_FAILURE,
                            "checkpoint publication failed",
                            failure),
                    manifestReplaced);
        }
    }

    private void writeManifestStaging(Path path, byte[] encoded) throws IOException {
        try (FileChannel channel = FileChannel.open(
                path,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE)) {
            if (DurableCrashHooks.active("v4-checkpoint-partial-manifest-v1")) {
                writeFully(channel, ByteBuffer.wrap(
                        encoded, 0, Math.max(1, encoded.length / 2)));
                DurableCrashHooks.reach("v4-checkpoint-partial-manifest-v1");
            }
            writeFully(channel, ByteBuffer.wrap(encoded));
            DurableIoFaults.fail("checkpoint-before-manifest-force");
            channel.force(true);
        }
    }

    private DurabilityException.Reason cleanupAfterPublication(
            DurableCheckpoint.Manifest authoritative
    ) {
        try {
            List<Path> candidates;
            try (var entries = Files.list(directory)) {
                candidates = entries.sorted().toList();
            }
            for (Path candidate : candidates) {
                String name = candidate.getFileName().toString();
                Matcher walMatcher = WAL_NAME.matcher(name);
                if (walMatcher.matches()) {
                    long generation = Long.parseLong(walMatcher.group(1));
                    if (generation < authoritative.walGeneration()) {
                        DurableIoFaults.fail("checkpoint-before-cleanup-delete");
                        Files.deleteIfExists(candidate);
                    }
                    continue;
                }
                if ((DurableCheckpoint.CHECKPOINT_FILE.matcher(name).matches()
                        && !name.equals(authoritative.checkpointFile()))
                        || DurableCheckpoint.CHECKPOINT_STAGING_FILE
                                .matcher(name).matches()
                        || name.equals(DurableCheckpoint.MANIFEST_STAGING_FILE)) {
                    DurableIoFaults.fail("checkpoint-before-cleanup-delete");
                    Files.deleteIfExists(candidate);
                }
            }
            DurableIoFaults.fail("checkpoint-before-cleanup-directory-force");
            forceDirectory(directory);
            return null;
        } catch (IOException | RuntimeException failure) {
            return DurabilityException.Reason.IO_FAILURE;
        }
    }

    private static void deleteStaging(Path path) throws IOException {
        Files.deleteIfExists(path);
    }

    private static void moveAtomic(
            Path source,
            Path destination,
            boolean replace
    ) throws IOException {
        try {
            if (replace) {
                Files.move(
                        source,
                        destination,
                        StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING);
            } else {
                Files.move(source, destination, StandardCopyOption.ATOMIC_MOVE);
            }
        } catch (AtomicMoveNotSupportedException failure) {
            throw new DurabilityException(
                    DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                    "durable storage requires same-filesystem atomic rename",
                    failure);
        }
    }

    private static void writeFully(FileChannel channel, ByteBuffer bytes)
            throws IOException {
        while (bytes.hasRemaining()) {
            int written = DurableIoFaults.write(channel, bytes);
            if (written <= 0) {
                throw new IOException("manifest write made no progress");
            }
        }
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
        if (!members.contains(METADATA_FILE)
                || members.stream().noneMatch(name -> WAL_NAME.matcher(name).matches())) {
            throw failure(
                    DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                    "initialized durable directory has missing authoritative members",
                    null);
        }
        for (String name : members) {
            if (!isEngineOwnedName(name)) {
                throw failure(
                        DurabilityException.Reason.INCOMPATIBLE_STORAGE,
                        "initialized durable directory has an unknown member",
                        null);
            }
            Path path = directory.resolve(name);
            if (Files.isSymbolicLink(path) || !Files.isRegularFile(path)) {
                throw failure(
                        DurabilityException.Reason.UNSUPPORTED_FILESYSTEM,
                        "durable storage members must be regular non-symbolic files",
                        null);
            }
        }
    }

    static String walFile(long generation) {
        if (generation <= 0) {
            throw new IllegalArgumentException("WAL generation must be positive");
        }
        return "gse-wal-%020d.log".formatted(generation);
    }

    private static List<WalMember> walMembers(
            Path directory,
            Set<String> members
    ) {
        List<WalMember> wals = new ArrayList<>();
        for (String name : members) {
            Matcher matcher = WAL_NAME.matcher(name);
            if (!matcher.matches()) {
                continue;
            }
            try {
                long generation = Long.parseLong(matcher.group(1));
                if (generation <= 0) {
                    throw new NumberFormatException("non-positive generation");
                }
                wals.add(new WalMember(generation, directory.resolve(name)));
            } catch (NumberFormatException failure) {
                throw new DurabilityException(
                        DurabilityException.Reason.CORRUPT_WAL,
                        "WAL filename generation is invalid",
                        failure);
            }
        }
        wals.sort(Comparator.comparingLong(WalMember::generation));
        if (wals.isEmpty()) {
            throw new DurabilityException(
                    DurabilityException.Reason.CORRUPT_WAL,
                    "initialized durable storage has no WAL generation");
        }
        return List.copyOf(wals);
    }

    private static boolean isEngineOwnedName(String name) {
        return name.equals(METADATA_FILE)
                || name.equals(METADATA_STAGING_FILE)
                || name.equals(DurableCheckpoint.MANIFEST_FILE)
                || name.equals(DurableCheckpoint.MANIFEST_STAGING_FILE)
                || WAL_NAME.matcher(name).matches()
                || DurableCheckpoint.CHECKPOINT_FILE.matcher(name).matches()
                || DurableCheckpoint.CHECKPOINT_STAGING_FILE.matcher(name).matches();
    }

    private static long retainedBytes(Path directory) throws IOException {
        try (var entries = Files.list(directory)) {
            return retainedBytesFromSnapshot(entries.toList());
        }
    }

    static long retainedBytesFromSnapshot(List<Path> entries) throws IOException {
        long retained = 0;
        for (Path path : entries) {
            String name = path.getFileName().toString();
            if (!isEngineOwnedName(name)) {
                continue;
            }
            try {
                BasicFileAttributes attributes = Files.readAttributes(
                        path, BasicFileAttributes.class);
                if (attributes.isRegularFile()) {
                    retained = Math.addExact(retained, attributes.size());
                }
            } catch (NoSuchFileException ignored) {
                // Checkpoint cleanup may remove a stale directory entry after
                // the snapshot was taken. Its retained contribution is zero.
            }
        }
        return retained;
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
                int written = DurableIoFaults.write(channel, buffer);
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
    public synchronized void close() {
        if (closed) {
            return;
        }
        closed = true;
        IOException primary = null;
        for (DurableWal replay : replayWals) {
            try {
                replay.close();
            } catch (IOException failure) {
                if (primary == null) {
                    primary = failure;
                } else {
                    primary.addSuppressed(failure);
                }
            }
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

    record GenerationCut(long generation, long firstSequence) {
        GenerationCut {
            if (generation <= 0 || firstSequence <= 0) {
                throw new IllegalArgumentException(
                        "checkpoint WAL boundary must be positive");
            }
        }
    }

    record CheckpointPublication(
            DurableCheckpoint.Manifest manifest,
            DurabilityException.Reason cleanupFailure
    ) {
        CheckpointPublication {
            Objects.requireNonNull(manifest, "manifest");
        }
    }

    static final class CheckpointFailure extends RuntimeException {
        private final DurabilityException failure;
        private final boolean manifestReplaced;

        CheckpointFailure(
                DurabilityException failure,
                boolean manifestReplaced
        ) {
            super(Objects.requireNonNull(failure, "failure"));
            this.failure = failure;
            this.manifestReplaced = manifestReplaced;
        }

        DurabilityException failure() {
            return failure;
        }

        boolean manifestReplaced() {
            return manifestReplaced;
        }
    }

    record OpenResult(
            DurableStorageOwner owner,
            List<DurableWal> wals,
            DurableCheckpoint.Manifest manifest,
            boolean fresh,
            long truncatedBytes
    ) {
        OpenResult {
            Objects.requireNonNull(owner, "owner");
            wals = List.copyOf(wals);
            if (wals.isEmpty()
                    || (fresh && (manifest != null || truncatedBytes != 0))
                    || truncatedBytes < 0) {
                throw new IllegalArgumentException("invalid durable open result");
            }
        }
    }

    private record WalMember(long generation, Path path) {
        WalMember {
            if (generation <= 0) {
                throw new IllegalArgumentException("invalid WAL member generation");
            }
            Objects.requireNonNull(path, "path");
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
