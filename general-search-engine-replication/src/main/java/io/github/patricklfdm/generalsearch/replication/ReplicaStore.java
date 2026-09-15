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

    static Set<String> files(int minor) {
        if (minor == 0) return FILES;
        var names = new java.util.HashSet<>(FILES);
        names.addAll(List.of("genesis.gsr", "bootstrap-prepared.gsr", "bootstrap-seal.gsr"));
        return Set.copyOf(names);
    }

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
    private final FileChannel promises;
    private FileChannel entries, proofs;
    private ReplicaGeneration.Selected selected;
    private long baseIndex;
    private boolean recoveryMode, damagedTail;
    private final boolean readOnly;
    private final Map<Long, UUID> promiseHistory = new HashMap<>();
    private final List<Long> entryOffsets = new ArrayList<>();
    private final List<Long> proofOffsets = new ArrayList<>();
    private long promisedEpoch = 1, lastEpoch = 1, commitIndex;
    private UUID incarnation = NO_INCARNATION;
    private String lastDigest;
    private UUID lastIncarnation = NO_INCARNATION;
    private boolean closed, failed, quiescing;
    private AdmissionNode.View admission;

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
        initialize(path, manifest, node, bounds, faults, false);
    }

    static void initializeReplacement(Path path, ReplicaManifest manifest, ReplicationNodeId node,
                                      ReplicationBounds bounds, Faults faults) {
        initialize(path, manifest, node, bounds, faults, true);
    }

    private static void initialize(Path path, ReplicaManifest manifest, ReplicationNodeId node,
                                   ReplicationBounds bounds, Faults faults, boolean replacement) {
        require(manifest.formatMinor() == 0, PROTOCOL_MISMATCH, "1.1 authority requires sealed offline admission");
        require(manifest.contains(node), PROTOCOL_MISMATCH, "local identity is not a manifest voter");
        byte[] manifestBytes = manifest.encode();
        String manifestDigest = frameDigest(manifestBytes);
        byte[] nodeBytes = frame(NODE, body(out -> {
            hash(out, manifestDigest);
            text(out, node.value());
            if (replacement) out.writeByte(1);
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
                if (replacement) {
                    try (var marker = FileChannel.open(directory.resolve(ReplicaGeneration.REBUILDING), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
                        writeAndForce(marker, ReplicaGeneration.rebuilding(manifest, node), "REBUILDING", faults);
                    }
                    forceDirectory(directory);
                }
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
        return load(directory, expected, node, bounds, faults, false, false);
    }

    static ReplicaStore openForRecovery(Path directory, ReplicaManifest expected, ReplicationNodeId node,
                                        ReplicationBounds bounds, Faults faults) {
        return load(directory, expected, node, bounds, faults, false, true);
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
        try (ReplicaStore store = load(directory, null, null, inspectionBounds, Faults.NONE, true, false)) {
            return new ReplicationStorageStatus(directory, true, true, Optional.of(store.manifest.groupId()),
                    Optional.of(store.node), "gse-replicated", 1, 0);
        }
    }

    private static ReplicaStore load(Path path, ReplicaManifest expected, ReplicationNodeId expectedNode,
                                     ReplicationBounds bounds, Faults faults, boolean readOnly, boolean recoveryMode) {
        return load(path, expected, expectedNode, bounds, faults, readOnly, recoveryMode, null, null);
    }

    static ReplicaStore openAdmitted(ReplicationGroupConfig<?, ?> config,
                                    io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<?, ?> application) {
        return load(config.replicaDirectory(), null, config.localNodeId(), config.bounds(), ReplicaRuntimeHooks.CURRENT.get().storage(),
                false, true, config, application);
    }

    private static ReplicaStore load(Path path, ReplicaManifest expected, ReplicationNodeId expectedNode,
            ReplicationBounds bounds, Faults faults, boolean readOnly, boolean recoveryMode,
            ReplicationGroupConfig<?, ?> config, io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration<?, ?> application) {
        int minor = config == null ? 0 : 1;
        Path directory = safePath(path);
        List<FileChannel> opened = new ArrayList<>();
        FileLock lock = null;
        try {
            require(Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS), STORAGE_FAILURE,
                    "replica directory is absent");
            validateFileSystem(directory);
            checkInventory(directory, minor);
            FileChannel lockChannel = FileChannel.open(directory.resolve(LOCK), readOnly
                    ? Set.of(StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)
                    : Set.of(StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS));
            opened.add(lockChannel);
            lock = acquire(lockChannel, readOnly);
            checkInventory(directory, minor);
            Frame manifestFrame = single(directory.resolve(MANIFEST_FILE), MANIFEST, minor);
            ReplicaManifest manifest = ReplicaManifest.decode(manifestFrame.body(), minor);
            require(manifest.digest().equals(manifestFrame.digest()), INTEGRITY_FAILURE,
                    "noncanonical manifest encoding");
            if (expected != null) {
                require(expected.digest().equals(manifestFrame.digest()), PROTOCOL_MISMATCH,
                        "replica manifest differs from expected immutable group");
            }
            Frame nodeFrame = single(directory.resolve(NODE_FILE), NODE, minor);
            var identity = input(nodeFrame.body());
            require(hash(identity).equals(manifestFrame.digest()), PROTOCOL_MISMATCH, "node manifest mismatch");
            var node = new ReplicationNodeId(text(identity, 64));
            int origin = minor == 1 || identity.available() > 0 ? identity.readUnsignedByte() : 0;
            require(origin <= 1 && (origin == 0 || Files.exists(directory.resolve(ReplicaGeneration.REBUILDING), LinkOption.NOFOLLOW_LINKS)),
                    INTEGRITY_FAILURE, "replacement identity marker is missing or invalid");
            end(identity);
            require(manifest.contains(node) && (expectedNode == null || expectedNode.equals(node)),
                    PROTOCOL_MISMATCH, "local voter identity mismatch");
            AdmissionNode.View admission = null;
            if (minor == 1) {
                admission = AdmissionNode.identity(directory);
                var expectedGroup = ReplicaManifest.from(config, ReplicaApplication.configurationDigest(application.indexes()));
                require(java.util.Arrays.equals(expectedGroup.encode(), admission.plan().manifest().group().encode()),
                        PROTOCOL_MISMATCH, "configured group differs from admitted authority");
                require(canonicalEqual(AdmissionConfiguration.application(application), admission.plan().descriptor().get("application")),
                        PROTOCOL_MISMATCH, "captured application differs from admitted authority");
                int localIndex = manifest.members().stream().map(ReplicationMember::nodeId).toList().indexOf(node);
                var actual = new java.util.TreeMap<>(AdmissionConfiguration.local(config));
                var sealed = new java.util.TreeMap<>(admission.plan().local(localIndex));
                // Absolute bootstrap paths are provenance: a sealed volume can be attached elsewhere.
                actual.remove("target"); sealed.remove("target");
                var actualCore = new java.util.TreeMap<>(AdmissionConfiguration.object(actual.get("materialization")));
                var sealedCore = new java.util.TreeMap<>(AdmissionConfiguration.object(sealed.get("materialization")));
                actualCore.remove("directory"); sealedCore.remove("directory");
                actual.put("materialization", actualCore); sealed.put("materialization", sealedCore);
                require(canonicalEqual(actual, sealed), PROTOCOL_MISMATCH, "local configuration differs from sealed admission");
            }
            ReplicaGeneration.validateRebuilding(directory, manifest, node);
            var selected = ReplicaGeneration.selected(directory, manifest, node, bounds);
            if (!readOnly && selected.snapshot() != null) ReplicaGeneration.ensureStarted(directory, manifest, node);
            var channels = new ArrayList<FileChannel>();
            for (String name : List.of(PROMISE_FILE, ENTRY_FILE, PROOF_FILE)) {
                FileChannel channel = FileChannel.open((name.equals(PROMISE_FILE) ? directory : selected.directory()).resolve(name), readOnly
                        ? Set.of(StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)
                        : Set.of(StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS));
                channels.add(channel);
                opened.add(channel);
            }
            var store = new ReplicaStore(directory, manifest, node, bounds, faults, lockChannel, lock,
                    channels.get(0), channels.get(1), channels.get(2), readOnly);
            store.selected = selected; store.recoveryMode = recoveryMode; store.admission = admission;
            store.scan(manifestFrame, nodeFrame);
            if (minor == 1) store.validateRetained();
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
        require(authoritativeBytes() <= bounds.maxRetainedLogBytes()
                        && retainedBytes() <= bounds.maxRetainedLogBytes() + bounds.maxSnapshotStagingBytes(), CAPACITY_EXCEEDED,
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
        Frame ready = single(directory.resolve(READY_FILE), READY, manifest.formatMinor());
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
            boolean initial = manifest.formatMinor() == 1 && promiseHistory.isEmpty() && epoch == 1 && incarnation.equals(NO_INCARNATION);
            require(initial || epoch > promisedEpoch && !incarnation.equals(NO_INCARNATION), INTEGRITY_FAILURE,
                    "promise ledger regresses or conflicts");
            promisedEpoch = epoch;
            this.incarnation = incarnation;
            promiseHistory.put(epoch, incarnation);
            offset = frame.nextOffset();
        }
        require(manifest.formatMinor() == 0 || promiseHistory.containsKey(1L), INTEGRITY_FAILURE, "genesis promise missing");
        if (selected.snapshot() != null) {
            baseIndex = selected.snapshot().index(); commitIndex = baseIndex;
            lastEpoch = selected.snapshot().epochAt(baseIndex); lastDigest = selected.snapshot().digestAt(baseIndex);
            lastIncarnation = baseIndex == 0 ? NO_INCARNATION : selected.snapshot().anchors().getLast().incarnation();
            require(lastEpoch <= promisedEpoch, INTEGRITY_FAILURE, "snapshot is newer than the root durable promise");
            require(ReplicaGeneration.floor(directory, manifest, node) <= baseIndex, INTEGRITY_FAILURE, "floor exceeds installed snapshot");
            ReplicaGeneration.validateFloor(directory, manifest, node, selected.snapshot());
        }
        offset = headers.get(1).nextOffset();
        while ((frame = readEntryForScan(offset)) != null) {
            require(lastLogIndex() < MAX_ENTRIES, CAPACITY_EXCEEDED, "entry count exceeds bound");
            ReplicaEntry entry = ReplicaEntry.decode(frame.body(), manifest.formatMinor());
            validateEntryChain(entry);
            require(entry.incarnation().equals(promiseHistory.get(entry.epoch()))
                            || selected.snapshot() != null && !promiseHistory.containsKey(entry.epoch()) && entry.epoch() < promisedEpoch, INTEGRITY_FAILURE,
                    "entry has no durable matching promise");
            rememberEntry(offset, entry, frame.digest());
            offset = frame.nextOffset();
        }
        offset = headers.get(2).nextOffset();
        while ((frame = read(proofs, offset, PROOF, MAX_METADATA_BYTES)) != null) {
            ReplicaProof proof = ReplicaProof.decode(frame.body(), manifest.formatMinor());
            require(proof.index() > commitIndex, INTEGRITY_FAILURE, "commit ledger regresses/duplicates");
            validateProof(proof);
            commitIndex = proof.index();
            proofOffsets.set(Math.toIntExact(commitIndex - baseIndex - 1), offset);
            offset = frame.nextOffset();
        }
    }

    /** Retained generations cannot hide a conflicting or newer durable proof behind the selected pointer. */
    private void validateRetained() throws IOException {
        var authoritative = image(genesisApplication());
        var anchors = authoritative.anchors();
        var sources = new ArrayList<Path>(); sources.add(directory);
        for (String slot : ReplicaGeneration.SLOTS) {
            Path source = directory.resolve(slot);
            if (Files.exists(source.resolve(ReplicaGeneration.SEAL), LinkOption.NOFOLLOW_LINKS)) {
                // Complete unselected slots must still be valid recovery sources. Incomplete staging is never authority.
                byte[] raw = ReplicaGeneration.bytes(source.resolve(ReplicaGeneration.SNAPSHOT), ReplicaSnapshot.maximum(bounds));
                var snapshot = ReplicaSnapshot.decode(raw, manifest, ReplicaSnapshot.maximum(bounds));
                require(snapshot.index() <= commitIndex && snapshot.digestAt(snapshot.index()).equals(digestAt(snapshot.index())),
                        CONFLICTING_HISTORY, "retained snapshot conflicts with selected committed history");
                require(snapshot.index() != 0 || java.util.Arrays.equals(snapshot.application(), genesisApplication()),
                        INTEGRITY_FAILURE, "retained genesis snapshot changed application");
                sources.add(source);
            }
        }
        for (Path source : sources) {
            if (source.equals(selected.directory())) continue;
            try (var channel = FileChannel.open(source.resolve(PROOF_FILE), StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
                Frame header = read(channel, 0, JOURNAL, MAX_METADATA_BYTES);
                require(header != null, INTEGRITY_FAILURE, "retained proof header missing");
                long offset = header.nextOffset(); Frame row;
                while ((row = read(channel, offset, PROOF, MAX_METADATA_BYTES)) != null) {
                    var proof = ReplicaProof.decode(row.body(), manifest.formatMinor());
                    require(proof.index() <= commitIndex, CONFLICTING_HISTORY, "selected generation lost a retained durable proof");
                    ReplicaSnapshot.validateProof(manifest, proof, proof.index(), anchors.get(Math.toIntExact(proof.index() - 1)), digestAt(proof.index() - 1));
                    offset = row.nextOffset();
                }
            }
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
        }), MAX_METADATA_BYTES, manifest.formatMinor());
        appendFrame(promises, bytes, "PROMISE");
        promisedEpoch = epoch;
        incarnation = requestedIncarnation;
        promiseHistory.put(epoch, incarnation);
        acknowledgementBarrier("PROMISE");
    }

    synchronized ReplicaProof.Receipt append(ReplicationNodeId sender, ReplicaEntry entry) {
        writable();
        leader(sender);
        require(!damagedTail, CONFLICTING_HISTORY, "entry tail requires fenced recovery installation");
        require(entry.formatMinor() == manifest.formatMinor() && entry.manifestDigest().equals(manifestDigest), PROTOCOL_MISMATCH, "entry group mismatch");
        active(entry.epoch(), entry.incarnation());
        byte[] bytes = entry.encode(bounds.maxFrameBytes());
        String digest = frameDigest(bytes);
        if (entry.index() <= lastLogIndex()) {
            try {
                require(readEntry(entry.index()).digest().equals(digest), CONFLICTING_HISTORY,
                        "same-index different-content entry");
            } catch (IOException error) {
                throw poison(error);
            }
            forceRetry(entries, "ENTRY");
            return ReplicaProof.acknowledgement(node, entry, digest);
        }
        require(lastLogIndex() < MAX_ENTRIES, CAPACITY_EXCEEDED, "entry count exceeds bound");
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
            if (proof.index() <= baseIndex) {
                require(proof.index() == baseIndex && frameDigest(bytes).equals(frameDigest(selected.snapshot().proof().encode())),
                        CONFLICTING_HISTORY, "retry predates retained proof ledger");
                forceRetry(proofs, "PROOF"); return frameDigest(bytes);
            }
            if (proof.index() <= commitIndex) {
                long offset = proofOffsets.get(Math.toIntExact(proof.index() - baseIndex - 1));
                require(offset >= 0 && readStored(proofs, offset, PROOF, MAX_METADATA_BYTES).digest().equals(frameDigest(bytes)),
                        CONFLICTING_HISTORY, "non-identical commit-proof retry");
                forceRetry(proofs, "PROOF");
                return frameDigest(bytes);
            }
            long offset = appendFrame(proofs, bytes, "PROOF");
            commitIndex = proof.index();
            proofOffsets.set(Math.toIntExact(commitIndex - baseIndex - 1), offset);
            acknowledgementBarrier("PROOF");
            return frameDigest(bytes);
        } catch (IOException error) {
            throw poison(error);
        }
    }

    private void validateEntryChain(ReplicaEntry entry) {
        require(entry.formatMinor() == manifest.formatMinor() && entry.manifestDigest().equals(manifestDigest), PROTOCOL_MISMATCH, "entry manifest mismatch");
        require(entry.index() == lastLogIndex() + 1 && entry.previousIndex() == lastLogIndex()
                        && entry.previousEpoch() == lastEpoch && entry.previousDigest().equals(lastDigest)
                        && entry.epoch() >= lastEpoch
                        && (entry.epoch() > lastEpoch || entry.incarnation().equals(lastIncarnation)),
                CONFLICTING_HISTORY, "entry is not a contiguous extension of the digest chain");
    }

    private void rememberEntry(long offset, ReplicaEntry entry, String digest) {
        entryOffsets.add(offset);
        proofOffsets.add(-1L);
        lastEpoch = entry.epoch();
        lastIncarnation = entry.incarnation();
        lastDigest = digest;
    }

    private Frame readEntry(long index) throws IOException {
        require(index > baseIndex && index <= lastLogIndex(), CONFLICTING_HISTORY,
                "referenced entry is missing");
        return readStored(entries, entryOffsets.get(Math.toIntExact(index - baseIndex - 1)), ENTRY, bounds.maxFrameBytes());
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
        require(proof.formatMinor() == manifest.formatMinor() && proof.manifestDigest().equals(manifestDigest), PROTOCOL_MISMATCH, "proof manifest mismatch");
        if (proof.index() <= baseIndex) {
            require(proof.index() >= 1, CONFLICTING_HISTORY, "invalid compacted proof index");
            ReplicaSnapshot.validateProof(manifest, proof, proof.index(), selected.snapshot().anchors().get(Math.toIntExact(proof.index() - 1)),
                    selected.snapshot().digestAt(proof.index() - 1));
            return;
        }
        Frame frame = readEntry(proof.index());
        ReplicaEntry entry;
        try {
            entry = ReplicaEntry.decode(frame.body(), manifest.formatMinor());
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
            require(authoritativeBytes() <= bounds.maxRetainedLogBytes() - bytes.length
                            && retainedBytes() <= bounds.maxRetainedLogBytes() + bounds.maxSnapshotStagingBytes() - bytes.length,
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
        require(!closed && !quiescing, CLOSED, "replica store is closed or quiescing");
        require(!failed, STORAGE_FAILURE, "replica store failed and must be reopened");
        require(!readOnly, STORAGE_FAILURE, "replica inspection is read-only");
    }

    /** Finish a current forced record before interrupting its writer; reject every later write. */
    synchronized void quiesce(Thread writer) {
        quiescing = true;
        if (writer != null && writer != Thread.currentThread()) writer.interrupt();
    }

    synchronized long lastLogIndex() { return baseIndex + entryOffsets.size(); }
    synchronized long snapshotIndex() { return baseIndex; }
    synchronized long recoveryFloor() {
        try { return ReplicaGeneration.floor(directory, manifest, node); }
        catch (IOException error) { throw poison(error); }
    }
    synchronized boolean voter() {
        return selected.snapshot() != null ? selected.admitted()
                : !Files.exists(directory.resolve(ReplicaGeneration.REBUILDING), LinkOption.NOFOLLOW_LINKS);
    }
    synchronized boolean damagedTail() { return damagedTail; }
    synchronized String digestAt(long index) {
        if (index <= baseIndex) return index == 0 ? manifestDigest : selected.snapshot().digestAt(index);
        try { return readEntry(index).digest(); }
        catch (IOException error) { throw poison(error); }
    }
    synchronized ReplicaProof proofAt(long index) {
        if (index == baseIndex) return selected.snapshot() == null ? null : selected.snapshot().proof();
        require(index > baseIndex && index <= lastLogIndex(), CONFLICTING_HISTORY, "proof index unavailable");
        try {
            long offset = proofOffsets.get(Math.toIntExact(index - baseIndex - 1));
            return offset < 0 ? null : ReplicaProof.decode(readStored(proofs, offset, PROOF, MAX_METADATA_BYTES).body(), manifest.formatMinor());
        } catch (IOException error) { throw poison(error); }
    }
    synchronized ReplicaRecoveryImage image(byte[] emptyApplication) {
        require(selected.snapshot() == null || selected.snapshot().index() != 0 || java.util.Arrays.equals(selected.snapshot().application(), emptyApplication),
                INTEGRITY_FAILURE, "index-zero snapshot differs from immutable genesis");
        var snapshot = selected.snapshot() == null ? new ReplicaSnapshot(manifestDigest, List.of(), null, emptyApplication, manifest.baseSequence(), manifest.formatMinor()) : selected.snapshot();
        var tail = new ArrayList<ReplicaEntry>(); var ledger = new ArrayList<ReplicaProof>();
        for (long index = baseIndex + 1; index <= commitIndex; index++) {
            tail.add(entryAt(index)); var proof = proofAt(index); if (proof != null) ledger.add(proof);
        }
        var image = new ReplicaRecoveryImage(snapshot, tail, ledger); image.validate(manifest, bounds); return image;
    }
    synchronized ReplicaRecoveryImage preserveSnapshot(ReplicaRecoveryImage image) {
        image.validate(manifest, bounds);
        require(manifest.formatMinor() == 0 || image.snapshot().index() != 0 || java.util.Arrays.equals(image.snapshot().application(), genesisApplication()),
                INTEGRITY_FAILURE, "index-zero recovery differs from immutable genesis");
        require(image.index() >= commitIndex && image.digestAt(commitIndex).equals(digestAt(commitIndex)),
                CONFLICTING_HISTORY, "recovery would discard protected local history");
        if (image.snapshot().index() < baseIndex) {
            require(image.digestAt(baseIndex).equals(selected.snapshot().digestAt(baseIndex)), CONFLICTING_HISTORY, "snapshot ancestry conflicts");
            image = new ReplicaRecoveryImage(selected.snapshot(), image.entries().stream().filter(entry -> entry.index() > baseIndex).toList(),
                    image.proofs().stream().filter(proof -> proof.index() > baseIndex).toList());
        }
        return image;
    }
    synchronized void install(ReplicaRecoveryImage image, long epoch, UUID requested, boolean admitReplacement) {
        writable(); active(epoch, requested); image = preserveSnapshot(image);
        require(image.anchors().stream().allMatch(anchor -> anchor.epoch() <= epoch), STALE_EPOCH, "recovery contains a newer epoch");
        // Every durable local proof is protected, including proofs whose ACK was lost.
        for (long index = baseIndex + 1; index <= commitIndex; index++) if (proofAt(index) != null)
            require(image.digestAt(index).equals(digestAt(index)), CONFLICTING_HISTORY, "recovery conflicts with a local proof");
        try {
            var next = ReplicaGeneration.install(directory, manifest, node, bounds, image, voter() || admitReplacement, faults);
            entries.close(); proofs.close(); selected = next;
            entries = FileChannel.open(next.directory().resolve(ENTRY_FILE), StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS);
            proofs = FileChannel.open(next.directory().resolve(PROOF_FILE), StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS);
            promiseHistory.clear(); entryOffsets.clear(); proofOffsets.clear();
            promisedEpoch = 1; incarnation = NO_INCARNATION; lastEpoch = 1; commitIndex = 0; baseIndex = 0; lastDigest = manifestDigest; damagedTail = false;
            lastIncarnation = NO_INCARNATION;
            scan(single(directory.resolve(MANIFEST_FILE), MANIFEST, manifest.formatMinor()), single(directory.resolve(NODE_FILE), NODE, manifest.formatMinor()));
        } catch (IOException error) { throw poison(error); }
        catch (RuntimeException error) { if (!(error instanceof ReplicationException r) || r.reason() != CAPACITY_EXCEEDED) failed = true; throw error; }
    }
    synchronized void checkpointLocal(ReplicaRecoveryImage image) {
        writable();
        require(!damagedTail && lastLogIndex() == commitIndex && image.index() == commitIndex
                && image.snapshot().index() == commitIndex && image.digestAt(commitIndex).equals(digestAt(commitIndex)),
                CONFLICTING_HISTORY, "local checkpoint requires a resolved committed cut");
        install(image, promisedEpoch, incarnation, false);
    }
    synchronized long checkpointSequence() { return selected.snapshot() == null ? manifest.baseSequence() : selected.snapshot().sequence(); }
    synchronized long journalGeneration() { return selected.generation(); }
    synchronized long journalRecords() { return entryOffsets.size(); }
    synchronized long journalBytes() {
        try { return Files.size(selected.directory().resolve(ENTRY_FILE)); } catch (IOException error) { throw poison(error); }
    }
    synchronized boolean failed() { return failed; }
    boolean emptyGenesis() { return admission == null || admission.plan().source().kind() == 0; }

    synchronized void advanceFloor(long index, String digest, List<ReplicationNodeId> voters) {
        writable();
        try { ReplicaGeneration.advanceFloor(directory, manifest, node, selected.snapshot(), index, digest, voters, faults); }
        catch (IOException error) { throw poison(error); }
    }
    synchronized void compact() {
        writable();
        try { ReplicaGeneration.compact(directory, selected, manifest, node, faults); }
        catch (IOException error) { throw poison(error); }
    }

    private Frame readEntryForScan(long offset) throws IOException {
        if (recoveryMode && entries.size() > offset) {
            long remaining = entries.size() - offset;
            if (remaining < HEADER_BYTES) { damagedTail = true; return null; }
            var header = ByteBuffer.allocate(16); int read = entries.read(header, offset);
            require(read == 16, INTEGRITY_FAILURE, "cannot read recovery entry header");
            int length = header.getInt(12);
            // Only a syntactically valid incomplete final ENTRY can await fenced repair.
            if (header.getInt(0) == MAGIC && header.getShort(4) == 1 && header.getShort(6) == manifest.formatMinor()
                    && header.getShort(8) == ENTRY && header.getShort(10) == 0 && length > 0
                    && (long) length + HEADER_BYTES <= bounds.maxFrameBytes() && (long) length + HEADER_BYTES > remaining) {
                damagedTail = true; return null;
            }
        }
        return read(entries, offset, ENTRY, bounds.maxFrameBytes());
    }
    synchronized ReplicaEntry entryAt(long index) {
        try { return ReplicaEntry.decode(readEntry(index).body(), manifest.formatMinor()); }
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
        return ReplicaGeneration.directoryBytes(directory);
    }

    private long authoritativeBytes() throws IOException {
        long bytes = 0;
        for (String file : files(manifest.formatMinor())) {
            if (selected.snapshot() != null && (file.equals(ENTRY_FILE) || file.equals(PROOF_FILE)))
                bytes += ReplicaGeneration.journalHeader(manifest, node, file.equals(ENTRY_FILE) ? ENTRY : PROOF).length;
            else bytes += Files.size(directory.resolve(file));
        }
        if (selected.snapshot() != null) bytes += ReplicaGeneration.directoryBytes(selected.directory());
        for (String name : List.of(ReplicaGeneration.CURRENT, ReplicaGeneration.FLOOR, ReplicaGeneration.REBUILDING, ReplicaGeneration.STARTED))
            if (Files.exists(directory.resolve(name), LinkOption.NOFOLLOW_LINKS)) bytes += Files.size(directory.resolve(name));
        return bytes;
    }

    private Frame read(FileChannel channel, long offset, int kind, int maximum) throws IOException {
        return ReplicaFormat.read(channel, offset, kind, maximum, manifest.formatMinor());
    }
    private static boolean canonicalEqual(Object left, Object right) {
        return java.util.Arrays.equals(ReplicaJson.encode(left, MAX_METADATA_BYTES), ReplicaJson.encode(right, MAX_METADATA_BYTES));
    }
    ReplicaManifest manifest() { return manifest; }
    Path directory() { return directory; }
    byte[] genesisApplication() {
        try { return AdmissionFormat.Genesis.read(admission.genesis(), admission.plan().manifest()).application(); }
        catch (IOException error) { throw failure(INTEGRITY_FAILURE, "invalid owned genesis", error); }
    }

    private static byte[] journalHeader(String digest, ReplicationNodeId node, int kind) {
        return frame(JOURNAL, body(out -> {
            hash(out, digest);
            text(out, node.value());
            out.writeShort(kind);
        }), MAX_METADATA_BYTES);
    }

    private static Frame single(Path path, int kind, int minor) throws IOException {
        try (var channel = FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            Frame frame = ReplicaFormat.read(channel, 0, kind, MAX_METADATA_BYTES, minor);
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

    private static void checkInventory(Path directory, int minor) throws IOException {
        var required = files(minor);
        try (var paths = Files.list(directory)) {
            var names = new java.util.HashSet<String>();
            var iterator = paths.iterator();
            while (iterator.hasNext()) {
                Path path = iterator.next(); String name = path.getFileName().toString();
                require(names.size() < required.size() + ReplicaGeneration.OPTIONAL.size(), INTEGRITY_FAILURE, "too many replica directory members");
                require(required.contains(name) || ReplicaGeneration.OPTIONAL.contains(name), INTEGRITY_FAILURE, "unknown replica member");
                if (ReplicaGeneration.SLOTS.contains(name)) ReplicaGeneration.inventorySlot(path, false);
                else if (name.equals(ReplicaTransfer.DIRECTORY)) ReplicaTransfer.inventory(path);
                else ReplicaGeneration.regular(path);
                names.add(name);
            }
            if (minor == 1 && names.containsAll(FILES) && !names.containsAll(required))
                single(directory.resolve(MANIFEST_FILE), MANIFEST, minor); // Explicitly reject historical 1.0 authority.
            require(names.containsAll(required), INTEGRITY_FAILURE, "replica inventory is incomplete");
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
