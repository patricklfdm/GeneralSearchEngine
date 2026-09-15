package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.OverlappingFileLockException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/** Local storage authority only. No transport, application apply or quorum coordinator. */
final class ReplicaStore implements AutoCloseable {
    static final String LOCK = "replica.lock", MANIFEST_FILE = "manifest.gsr", NODE_FILE = "node.gsr";
    static final String PROMISE_FILE = "promises.gsr", ENTRY_FILE = "entries.gsr", PROOF_FILE = "proofs.gsr";
    static final String READY_FILE = "storage-ready.gsr";
    static final Set<String> FILES = Set.of(LOCK, MANIFEST_FILE, NODE_FILE, PROMISE_FILE,
            ENTRY_FILE, PROOF_FILE, READY_FILE);

    interface Faults {
        Faults NONE = new Faults() { };
        default void at(String barrier) throws IOException { }
        default int maxWriteBytes() { return Integer.MAX_VALUE; }
    }

    private final Path directory;
    private final ReplicaManifest manifest;
    private final String manifestDigest;
    private final ReplicationNodeId node;
    private final ReplicationBounds bounds;
    private final Faults faults;
    private final FileChannel lockChannel;
    private final FileLock lock;
    private final FileChannel promises, entries, proofs;
    private final boolean readOnly;
    private final Map<Long, UUID> promiseHistory = new HashMap<>();
    private final List<Long> entryOffsets = new ArrayList<>();
    private final List<Long> proofOffsets = new ArrayList<>();
    private long promisedEpoch = 1, lastEpoch = 1, commitIndex;
    private UUID incarnation = NO_INCARNATION;
    private String lastDigest;
    private boolean closed, failed;

    private ReplicaStore(Path directory, ReplicaManifest manifest, ReplicationNodeId node,
                         ReplicationBounds bounds, Faults faults, FileChannel lockChannel, FileLock lock,
                         FileChannel promises, FileChannel entries, FileChannel proofs, boolean readOnly) {
        this.directory = directory;
        this.manifest = manifest;
        this.manifestDigest = manifest.digest();
        this.node = node;
        this.bounds = bounds;
        this.faults = faults;
        this.lockChannel = lockChannel;
        this.lock = lock;
        this.promises = promises;
        this.entries = entries;
        this.proofs = proofs;
        this.readOnly = readOnly;
        this.lastDigest = manifestDigest;
    }

    /** Storage initialization primitive for a future reviewed group bootstrap. */
    static void initialize(Path path, ReplicaManifest manifest, ReplicationNodeId node,
                           ReplicationBounds bounds, Faults faults) {
        require(manifest.contains(node), PROTOCOL_MISMATCH, "local identity is not a manifest voter");
        byte[] manifestBytes = manifest.encode();
        String manifestDigest = frameDigest(manifestBytes);
        byte[] nodeBytes = frame(NODE, body(out -> {
            hash(out, manifestDigest);
            text(out, node.value());
        }), MAX_METADATA_BYTES);
        Map<String, byte[]> files = new LinkedHashMap<>();
        files.put(MANIFEST_FILE, manifestBytes);
        files.put(NODE_FILE, nodeBytes);
        files.put(PROMISE_FILE, journalHeader(manifestDigest, node, PROMISE));
        files.put(ENTRY_FILE, journalHeader(manifestDigest, node, ENTRY));
        files.put(PROOF_FILE, journalHeader(manifestDigest, node, PROOF));
        files.put(READY_FILE, frame(READY, body(out -> {
            for (byte[] bytes : List.copyOf(files.values())) {
                hash(out, frameDigest(bytes));
            }
        }), MAX_METADATA_BYTES));
        require(files.values().stream().mapToLong(bytes -> bytes.length).sum() <= bounds.maxRetainedLogBytes(),
                CAPACITY_EXCEEDED, "initial replica metadata exceeds retained-byte bound");
        Path directory = safePath(path);
        require(!Files.exists(directory, LinkOption.NOFOLLOW_LINKS), STORAGE_FAILURE,
                "replica initialization requires an absent target");
        try {
            require(Files.isDirectory(directory.getParent(), LinkOption.NOFOLLOW_LINKS), STORAGE_FAILURE,
                    "replica parent directory must already exist");
            validateFileSystem(directory.getParent());
            Files.createDirectory(directory);
            forceDirectory(directory.getParent());
            try (var channel = FileChannel.open(directory.resolve(LOCK), StandardOpenOption.CREATE_NEW,
                    StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS);
                 var ignored = acquire(channel, false)) {
                channel.force(true);
                for (var item : files.entrySet()) {
                    try (var member = FileChannel.open(directory.resolve(item.getKey()),
                            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
                        writeAndForce(member, item.getValue(), "INIT_" + item.getKey(), faults);
                    }
                    forceDirectory(directory);
                }
            }
        } catch (IOException error) {
            throw failure(STORAGE_FAILURE, "replica initialization failed; partial target retained", error);
        }
    }

    static ReplicaStore open(Path directory, ReplicaManifest expected, ReplicationNodeId node,
                             ReplicationBounds bounds, Faults faults) {
        return load(directory, expected, node, bounds, faults, false);
    }

    static ReplicationStorageStatus inspect(Path path) {
        Path directory = safePath(path);
        if (!Files.exists(directory, LinkOption.NOFOLLOW_LINKS)) {
            return new ReplicationStorageStatus(directory, false, false, Optional.empty(), Optional.empty(),
                    "gse-replicated", 1, 0);
        }
        ReplicationBounds defaults = ReplicationBounds.defaults();
        var inspectionBounds = new ReplicationBounds(ReplicationBounds.HARD_MAX_FRAME_BYTES,
                defaults.maxEntriesPerAppend(), defaults.maxInFlightPerPeer(), defaults.maxPendingClientOperations(),
                defaults.maxRetryAttempts(), defaults.requestTimeoutMillis(), defaults.retryBackoffMillis(),
                defaults.snapshotChunkBytes(), ReplicationBounds.HARD_MAX_RETAINED_LOG_BYTES,
                defaults.maxSnapshotStagingBytes());
        try (ReplicaStore store = load(directory, null, null, inspectionBounds, Faults.NONE, true)) {
            return new ReplicationStorageStatus(directory, true, true, Optional.of(store.manifest.groupId()),
                    Optional.of(store.node), "gse-replicated", 1, 0);
        }
    }

    private static ReplicaStore load(Path path, ReplicaManifest expected, ReplicationNodeId expectedNode,
                                     ReplicationBounds bounds, Faults faults, boolean readOnly) {
        Path directory = safePath(path);
        List<FileChannel> opened = new ArrayList<>();
        FileLock lock = null;
        try {
            require(Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS), STORAGE_FAILURE,
                    "replica directory is absent");
            validateFileSystem(directory);
            checkInventory(directory);
            FileChannel lockChannel = FileChannel.open(directory.resolve(LOCK), readOnly
                    ? Set.of(StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)
                    : Set.of(StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS));
            opened.add(lockChannel);
            lock = acquire(lockChannel, readOnly);
            checkInventory(directory);
            Frame manifestFrame = single(directory.resolve(MANIFEST_FILE), MANIFEST);
            ReplicaManifest manifest = ReplicaManifest.decode(manifestFrame.body());
            require(manifest.digest().equals(manifestFrame.digest()), INTEGRITY_FAILURE,
                    "noncanonical manifest encoding");
            if (expected != null) {
                require(expected.digest().equals(manifestFrame.digest()), PROTOCOL_MISMATCH,
                        "replica manifest differs from expected immutable group");
            }
            Frame nodeFrame = single(directory.resolve(NODE_FILE), NODE);
            var identity = input(nodeFrame.body());
            require(hash(identity).equals(manifestFrame.digest()), PROTOCOL_MISMATCH, "node manifest mismatch");
            var node = new ReplicationNodeId(text(identity, 64));
            end(identity);
            require(manifest.contains(node) && (expectedNode == null || expectedNode.equals(node)),
                    PROTOCOL_MISMATCH, "local voter identity mismatch");
            var channels = new ArrayList<FileChannel>();
            for (String name : List.of(PROMISE_FILE, ENTRY_FILE, PROOF_FILE)) {
                FileChannel channel = FileChannel.open(directory.resolve(name), readOnly
                        ? Set.of(StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)
                        : Set.of(StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS));
                channels.add(channel);
                opened.add(channel);
            }
            var store = new ReplicaStore(directory, manifest, node, bounds, faults, lockChannel, lock,
                    channels.get(0), channels.get(1), channels.get(2), readOnly);
            store.scan(manifestFrame, nodeFrame);
            return store;
        } catch (IOException | RuntimeException error) {
            if (lock != null) {
                try { lock.release(); } catch (IOException suppressed) { error.addSuppressed(suppressed); }
            }
            for (FileChannel channel : opened) {
                try { channel.close(); } catch (IOException suppressed) { error.addSuppressed(suppressed); }
            }
            if (error instanceof ReplicationException classified) {
                throw classified;
            }
            throw failure(error instanceof IOException && !(error instanceof java.io.EOFException)
                    && !(error instanceof java.nio.charset.CharacterCodingException)
                    ? STORAGE_FAILURE : INTEGRITY_FAILURE, "cannot open replicated storage", error);
        }
    }

    private void scan(Frame manifestFrame, Frame nodeFrame) throws IOException {
        require(retainedBytes() <= bounds.maxRetainedLogBytes(), CAPACITY_EXCEEDED,
                "replica directory exceeds retained-byte bound");
        var headers = new ArrayList<Frame>();
        int[] kinds = {PROMISE, ENTRY, PROOF};
        int cursor = 0;
        for (FileChannel channel : List.of(promises, entries, proofs)) {
            Frame header = read(channel, 0, JOURNAL, MAX_METADATA_BYTES);
            require(header != null, INTEGRITY_FAILURE, "missing replica journal header");
            var input = input(header.body());
            require(hash(input).equals(manifestDigest) && text(input, 64).equals(node.value())
                            && input.readUnsignedShort() == kinds[cursor++],
                    PROTOCOL_MISMATCH, "journal identity/kind mismatch");
            end(input);
            headers.add(header);
        }
        Frame ready = single(directory.resolve(READY_FILE), READY);
        var readyInput = input(ready.body());
        for (Frame frame : List.of(manifestFrame, nodeFrame, headers.get(0), headers.get(1), headers.get(2))) {
            require(hash(readyInput).equals(frame.digest()), INTEGRITY_FAILURE, "incomplete storage initialization");
        }
        end(readyInput);
        long offset = headers.get(0).nextOffset();
        Frame frame;
        while ((frame = read(promises, offset, PROMISE, MAX_METADATA_BYTES)) != null) {
            require(promiseHistory.size() < MAX_PROMISES, CAPACITY_EXCEEDED, "promise count exceeds bound");
            var input = input(frame.body());
            require(hash(input).equals(manifestDigest) && text(input, 64).equals(manifest.leader().value()),
                    PROTOCOL_MISMATCH, "promise group/leader mismatch");
            long epoch = input.readLong();
            UUID incarnation = uuid(input);
            end(input);
            require(epoch > promisedEpoch && !incarnation.equals(NO_INCARNATION), INTEGRITY_FAILURE,
                    "promise ledger regresses or conflicts");
            promisedEpoch = epoch;
            this.incarnation = incarnation;
            promiseHistory.put(epoch, incarnation);
            offset = frame.nextOffset();
        }
        offset = headers.get(1).nextOffset();
        while ((frame = read(entries, offset, ENTRY, bounds.maxFrameBytes())) != null) {
            require(entryOffsets.size() < MAX_ENTRIES, CAPACITY_EXCEEDED, "entry count exceeds bound");
            ReplicaEntry entry = ReplicaEntry.decode(frame.body());
            validateEntryChain(entry);
            require(entry.incarnation().equals(promiseHistory.get(entry.epoch())), INTEGRITY_FAILURE,
                    "entry has no durable matching promise");
            rememberEntry(offset, entry, frame.digest());
            offset = frame.nextOffset();
        }
        offset = headers.get(2).nextOffset();
        while ((frame = read(proofs, offset, PROOF, MAX_METADATA_BYTES)) != null) {
            ReplicaProof proof = ReplicaProof.decode(frame.body());
            require(proof.index() > commitIndex, INTEGRITY_FAILURE, "commit ledger regresses/duplicates");
            validateProof(proof);
            commitIndex = proof.index();
            proofOffsets.set((int) commitIndex - 1, offset);
            offset = frame.nextOffset();
        }
    }

    synchronized void promise(ReplicationNodeId sender, long epoch, UUID requestedIncarnation) {
        writable();
        leader(sender);
        require(epoch >= 2 && requestedIncarnation != null && !requestedIncarnation.equals(NO_INCARNATION),
                STALE_EPOCH, "invalid activation epoch/incarnation");
        require(epoch > promisedEpoch || (epoch == promisedEpoch && requestedIncarnation.equals(incarnation)),
                STALE_EPOCH, "stale or conflicting epoch promise");
        if (epoch == promisedEpoch) {
            forceRetry(promises, "PROMISE");
            return;
        }
        require(promiseHistory.size() < MAX_PROMISES, CAPACITY_EXCEEDED, "promise count exceeds bound");
        byte[] bytes = frame(PROMISE, body(out -> {
            hash(out, manifestDigest);
            text(out, sender.value());
            out.writeLong(epoch);
            uuid(out, requestedIncarnation);
        }), MAX_METADATA_BYTES);
        appendFrame(promises, bytes, "PROMISE");
        promisedEpoch = epoch;
        incarnation = requestedIncarnation;
        promiseHistory.put(epoch, incarnation);
        acknowledgementBarrier("PROMISE");
    }

    synchronized ReplicaProof.Receipt append(ReplicationNodeId sender, ReplicaEntry entry) {
        writable();
        leader(sender);
        require(entry.manifestDigest().equals(manifestDigest), PROTOCOL_MISMATCH, "entry group mismatch");
        active(entry.epoch(), entry.incarnation());
        byte[] bytes = entry.encode(bounds.maxFrameBytes());
        String digest = frameDigest(bytes);
        if (entry.index() <= entryOffsets.size()) {
            try {
                require(readEntry(entry.index()).digest().equals(digest), CONFLICTING_HISTORY,
                        "same-index different-content entry");
            } catch (IOException error) {
                throw poison(error);
            }
            forceRetry(entries, "ENTRY");
            return ReplicaProof.acknowledgement(node, entry, digest);
        }
        require(entryOffsets.size() < MAX_ENTRIES, CAPACITY_EXCEEDED, "entry count exceeds bound");
        validateEntryChain(entry);
        long offset = appendFrame(entries, bytes, "ENTRY");
        rememberEntry(offset, entry, digest);
        acknowledgementBarrier("ENTRY");
        return ReplicaProof.acknowledgement(node, entry, digest);
    }

    synchronized String storeProof(ReplicationNodeId sender, ReplicaProof proof) {
        writable();
        leader(sender);
        active(proof.epoch(), proof.incarnation());
        try {
            validateProof(proof);
            byte[] bytes = proof.encode();
            if (proof.index() <= commitIndex) {
                long offset = proofOffsets.get((int) proof.index() - 1);
                require(offset >= 0 && readStored(proofs, offset, PROOF, MAX_METADATA_BYTES).digest().equals(frameDigest(bytes)),
                        CONFLICTING_HISTORY, "non-identical commit-proof retry");
                forceRetry(proofs, "PROOF");
                return frameDigest(bytes);
            }
            long offset = appendFrame(proofs, bytes, "PROOF");
            commitIndex = proof.index();
            proofOffsets.set((int) commitIndex - 1, offset);
            acknowledgementBarrier("PROOF");
            return frameDigest(bytes);
        } catch (IOException error) {
            throw poison(error);
        }
    }

    private void validateEntryChain(ReplicaEntry entry) {
        require(entry.manifestDigest().equals(manifestDigest), PROTOCOL_MISMATCH, "entry manifest mismatch");
        require(entry.index() == entryOffsets.size() + 1L && entry.previousIndex() == entryOffsets.size()
                        && entry.previousEpoch() == lastEpoch && entry.previousDigest().equals(lastDigest)
                        && entry.epoch() >= lastEpoch,
                CONFLICTING_HISTORY, "entry is not a contiguous extension of the digest chain");
    }

    private void rememberEntry(long offset, ReplicaEntry entry, String digest) {
        entryOffsets.add(offset);
        proofOffsets.add(-1L);
        lastEpoch = entry.epoch();
        lastDigest = digest;
    }

    private Frame readEntry(long index) throws IOException {
        require(index >= 1 && index <= entryOffsets.size(), CONFLICTING_HISTORY,
                "referenced entry is missing");
        return readStored(entries, entryOffsets.get((int) index - 1), ENTRY, bounds.maxFrameBytes());
    }

    private Frame readStored(FileChannel channel, long offset, int kind, int maximum) throws IOException {
        try {
            Frame frame = read(channel, offset, kind, maximum);
            require(frame != null, INTEGRITY_FAILURE, "stored record disappeared while owned");
            return frame;
        } catch (ReplicationException error) {
            failed = true;
            throw error;
        }
    }

    private void validateProof(ReplicaProof proof) throws IOException {
        require(proof.manifestDigest().equals(manifestDigest), PROTOCOL_MISMATCH, "proof manifest mismatch");
        Frame frame = readEntry(proof.index());
        ReplicaEntry entry;
        try {
            entry = ReplicaEntry.decode(frame.body());
        } catch (IOException | IllegalArgumentException | ReplicationException error) {
            failed = true;
            throw failure(INTEGRITY_FAILURE, "stored entry fields are invalid", error);
        }
        require(proof.entryDigest().equals(frame.digest()) && proof.epoch() == entry.epoch()
                        && proof.incarnation().equals(entry.incarnation())
                        && proof.previousDigest().equals(entry.previousDigest()),
                CONFLICTING_HISTORY, "proof does not bind the exact entry and predecessor");
        for (ReplicaProof.Receipt receipt : proof.receipts()) {
            require(manifest.contains(receipt.voter()), PROTOCOL_MISMATCH, "proof voter is not in manifest");
            require(ReplicaProof.acknowledgement(receipt.voter(), entry, frame.digest()).equals(receipt),
                    INTEGRITY_FAILURE, "invalid durable-entry receipt digest");
        }
    }

    private void active(long epoch, UUID incarnation) {
        require(epoch == promisedEpoch && this.incarnation.equals(incarnation), STALE_EPOCH,
                "request does not match the durable epoch/incarnation promise");
    }

    private void leader(ReplicationNodeId sender) {
        require(manifest.leader().equals(sender), NOT_CONFIGURED_LEADER, "sender is not configured leader");
    }

    private long appendFrame(FileChannel channel, byte[] bytes, String operation) {
        try {
            require(retainedBytes() <= bounds.maxRetainedLogBytes() - bytes.length,
                    CAPACITY_EXCEEDED, "replica journals exceed retained-byte bound");
            long offset = channel.size();
            channel.position(offset);
            writeAndForce(channel, bytes, operation, faults);
            return offset;
        } catch (IOException error) {
            throw poison(error);
        }
    }

    private void forceRetry(FileChannel channel, String operation) {
        try {
            faults.at("BEFORE_" + operation + "_FORCE");
            channel.force(true);
            faults.at("AFTER_" + operation + "_FORCE");
            acknowledgementBarrier(operation);
        } catch (IOException error) {
            throw poison(error);
        }
    }

    private void acknowledgementBarrier(String operation) {
        try {
            faults.at("BEFORE_" + operation + "_ACK");
        } catch (IOException error) {
            throw poison(error);
        }
    }

    private ReplicationException poison(IOException error) {
        failed = true;
        return failure(STORAGE_FAILURE, "replica I/O failed; reopen is required", error);
    }

    private void writable() {
        require(!closed, CLOSED, "replica store is closed");
        require(!failed, STORAGE_FAILURE, "replica store failed and must be reopened");
        require(!readOnly, STORAGE_FAILURE, "replica inspection is read-only");
    }

    synchronized long lastLogIndex() { return entryOffsets.size(); }
    synchronized ReplicaEntry entryAt(long index) {
        try { return ReplicaEntry.decode(readEntry(index).body()); }
        catch (IOException error) { throw poison(error); }
        catch (IllegalArgumentException error) {
            failed = true;
            throw failure(INTEGRITY_FAILURE, "stored entry fields are invalid", error);
        }
    }
    synchronized long retainedLogBytes() {
        try { return retainedBytes(); }
        catch (IOException error) { throw poison(error); }
    }
    synchronized long commitIndex() { return commitIndex; }
    synchronized long promisedEpoch() { return promisedEpoch; }
    synchronized String lastEntryDigest() { return lastDigest; }
    synchronized long lastEntryEpoch() { return lastEpoch; }

    private long retainedBytes() throws IOException {
        long bytes = 0;
        for (String file : FILES) {
            bytes = Math.addExact(bytes, Files.size(directory.resolve(file)));
        }
        return bytes;
    }

    private static byte[] journalHeader(String digest, ReplicationNodeId node, int kind) {
        return frame(JOURNAL, body(out -> {
            hash(out, digest);
            text(out, node.value());
            out.writeShort(kind);
        }), MAX_METADATA_BYTES);
    }

    private static Frame single(Path path, int kind) throws IOException {
        try (var channel = FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            Frame frame = read(channel, 0, kind, MAX_METADATA_BYTES);
            require(frame != null && frame.nextOffset() == channel.size(), INTEGRITY_FAILURE,
                    "metadata must contain exactly one complete frame");
            return frame;
        }
    }

    private static void writeAndForce(FileChannel channel, byte[] bytes, String operation,
                                      Faults faults) throws IOException {
        faults.at("BEFORE_" + operation + "_WRITE");
        ByteBuffer buffer = ByteBuffer.wrap(bytes);
        int maximum = faults.maxWriteBytes();
        if (maximum <= 0) {
            throw new IOException("invalid write chunk size");
        }
        int stalls = 0;
        while (buffer.hasRemaining()) {
            int limit = buffer.limit();
            buffer.limit(buffer.position() + Math.min(buffer.remaining(), maximum));
            int written = channel.write(buffer);
            buffer.limit(limit);
            if (written == 0 && ++stalls > 16) {
                throw new IOException("replica write made no progress");
            }
            if (written > 0) {
                stalls = 0;
            }
            faults.at("AFTER_" + operation + "_WRITE_CHUNK");
        }
        faults.at("BEFORE_" + operation + "_FORCE");
        channel.force(true);
        faults.at("AFTER_" + operation + "_FORCE");
    }

    private static FileLock acquire(FileChannel channel, boolean readOnly) throws IOException {
        try {
            FileLock lock = channel.tryLock(0, Long.MAX_VALUE, readOnly);
            require(lock != null, STORAGE_FAILURE, "replica directory has another owner");
            return lock;
        } catch (OverlappingFileLockException error) {
            throw failure(STORAGE_FAILURE, "replica directory has another owner", error);
        }
    }

    private static Path safePath(Path path) {
        Path absolute = path.toAbsolutePath();
        Path cursor = absolute.getRoot();
        for (Path part : absolute) {
            cursor = cursor.resolve(part);
            require(!Files.isSymbolicLink(cursor), STORAGE_FAILURE, "replica path contains a symbolic link");
        }
        return absolute.normalize();
    }

    private static void checkInventory(Path directory) throws IOException {
        try (var paths = Files.list(directory)) {
            var names = new java.util.HashSet<String>();
            var iterator = paths.iterator();
            while (iterator.hasNext()) {
                Path path = iterator.next();
                require(names.size() < FILES.size(), INTEGRITY_FAILURE, "too many replica directory members");
                require(Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE,
                        "non-regular replica member");
                if (Files.getFileStore(path).supportsFileAttributeView("unix")) {
                    require(((Number) Files.getAttribute(path, "unix:nlink", LinkOption.NOFOLLOW_LINKS)).longValue() == 1,
                            INTEGRITY_FAILURE, "replica member has multiple hard links");
                }
                names.add(path.getFileName().toString());
            }
            require(names.equals(FILES), INTEGRITY_FAILURE, "replica inventory is incomplete or contains unknown members");
            require(Files.size(directory.resolve(LOCK)) == 0, INTEGRITY_FAILURE, "replica lock file is not empty");
        }
    }

    private static void validateFileSystem(Path directory) throws IOException {
        String type = Files.getFileStore(directory).type().toLowerCase(Locale.ROOT);
        for (String unsupported : List.of("nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p")) {
            require(!type.contains(unsupported), STORAGE_FAILURE, "unsupported replica filesystem: " + type);
        }
    }

    private static void forceDirectory(Path directory) throws IOException {
        try (var channel = FileChannel.open(directory, StandardOpenOption.READ)) {
            channel.force(true);
        }
    }

    @Override
    public synchronized void close() {
        if (closed) {
            return;
        }
        closed = true;
        IOException failure = null;
        for (FileChannel channel : List.of(promises, entries, proofs)) {
            try { channel.close(); } catch (IOException error) {
                if (failure == null) { failure = error; } else { failure.addSuppressed(error); }
            }
        }
        try { lock.release(); } catch (IOException error) {
            if (failure == null) { failure = error; } else { failure.addSuppressed(error); }
        }
        try { lockChannel.close(); } catch (IOException error) {
            if (failure == null) { failure = error; } else { failure.addSuppressed(error); }
        }
        if (failure != null) {
            throw failure(STORAGE_FAILURE, "cannot close replica storage", failure);
        }
    }
}
