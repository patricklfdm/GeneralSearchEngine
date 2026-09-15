package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/** Two generation slots, one forced atomic selector, and exact cleanup under the root owner lock. */
final class ReplicaGeneration {
    static final String CURRENT = "current.gsr", PENDING = "current.pending.gsr", FLOOR = "recovery-floor.gsr";
    static final String REBUILDING = "rebuilding.gsr", SNAPSHOT = "snapshot.gsr", SEAL = "generation.gsr";
    static final String STARTED = "generation-started.gsr";
    static final Set<String> SLOTS = Set.of("generation-a", "generation-b");
    static final Set<String> MEMBERS = Set.of(SNAPSHOT, ReplicaStore.ENTRY_FILE, ReplicaStore.PROOF_FILE, SEAL);
    static final Set<String> OPTIONAL = Set.of(CURRENT, PENDING, FLOOR, "recovery-floor.pending.gsr", REBUILDING, STARTED, "generation-a", "generation-b", ReplicaTransfer.DIRECTORY);
    private static final int POINTER_KIND = 10, SEAL_KIND = 11, FLOOR_KIND = 12, REBUILD_KIND = 13;
    record Selected(Path directory, ReplicaSnapshot snapshot, boolean admitted) { }
    private ReplicaGeneration() { }

    static Selected selected(Path root, ReplicaManifest manifest, ReplicationNodeId node, ReplicationBounds bounds) throws IOException {
        boolean started = Files.exists(root.resolve(STARTED), LinkOption.NOFOLLOW_LINKS);
        if (started) {
            var marker = input(read(root.resolve(STARTED), 15, MAX_METADATA_BYTES));
            require(hash(marker).equals(manifest.digest()) && text(marker, 64).equals(node.value()), PROTOCOL_MISMATCH, "generation-started identity mismatch"); end(marker);
        }
        if (!Files.exists(root.resolve(CURRENT), LinkOption.NOFOLLOW_LINKS)) {
            require(!started && !Files.exists(root.resolve(FLOOR), LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE, "installed generation selector is missing");
            return new Selected(root, null, false);
        }
        var pointer = input(read(root.resolve(CURRENT), POINTER_KIND, MAX_METADATA_BYTES));
        require(hash(pointer).equals(manifest.digest()) && text(pointer, 64).equals(node.value()), PROTOCOL_MISMATCH, "generation pointer identity mismatch");
        String slot = text(pointer, 32); UUID generation = uuid(pointer); String sealDigest = hash(pointer);
        int admittedFlag = pointer.readUnsignedByte(); require(admittedFlag <= 1, INTEGRITY_FAILURE, "invalid generation admission flag");
        boolean admitted = admittedFlag == 1; end(pointer);
        require(SLOTS.contains(slot), INTEGRITY_FAILURE, "unknown generation slot");
        Path directory = root.resolve(slot); inventorySlot(directory, true);
        byte[] sealBytes = bytes(directory.resolve(SEAL), MAX_METADATA_BYTES);
        require(frameDigest(sealBytes).equals(sealDigest), INTEGRITY_FAILURE, "generation selector/seal mismatch");
        var seal = input(decodeRecord(sealBytes, SEAL_KIND, MAX_METADATA_BYTES));
        require(hash(seal).equals(manifest.digest()) && text(seal, 64).equals(node.value()) && uuid(seal).equals(generation),
                PROTOCOL_MISMATCH, "generation seal identity mismatch");
        byte[] snapshotBytes = bytes(directory.resolve(SNAPSHOT), ReplicaSnapshot.maximum(bounds));
        require(hash(seal).equals(frameDigest(snapshotBytes)), INTEGRITY_FAILURE, "generation snapshot digest mismatch");
        for (String journal : List.of(ReplicaStore.ENTRY_FILE, ReplicaStore.PROOF_FILE)) {
            try (var channel = FileChannel.open(directory.resolve(journal), StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
                var header = ReplicaFormat.read(channel, 0, JOURNAL, MAX_METADATA_BYTES);
                require(header != null && hash(seal).equals(header.digest()), INTEGRITY_FAILURE, "generation journal header mismatch");
            }
        }
        end(seal);
        return new Selected(directory, ReplicaSnapshot.decode(snapshotBytes, manifest, ReplicaSnapshot.maximum(bounds)), admitted);
    }

    static Selected install(Path root, ReplicaManifest manifest, ReplicationNodeId node, ReplicationBounds bounds,
                            ReplicaRecoveryImage image, boolean admitted, ReplicaStore.Faults faults) throws IOException {
        image.validate(manifest, bounds);
        byte[] snapshot = image.snapshot().encode(ReplicaSnapshot.maximum(bounds));
        long stagedBytes = snapshot.length + journalHeader(manifest.digest(), node, ENTRY).length
                + journalHeader(manifest.digest(), node, PROOF).length + 196 + node.value().getBytes(java.nio.charset.StandardCharsets.UTF_8).length;
        for (var entry : image.entries()) stagedBytes = Math.addExact(stagedBytes, entry.encodedLength());
        for (var proof : image.proofs()) stagedBytes = Math.addExact(stagedBytes, proof.encode().length);
        long rootMetadata = 4096; // selector, started/floor markers and temporary atomic-write metadata
        for (String file : ReplicaStore.FILES) if (!file.equals(ReplicaStore.ENTRY_FILE) && !file.equals(ReplicaStore.PROOF_FILE)) rootMetadata += Files.size(root.resolve(file));
        require(stagedBytes <= bounds.maxSnapshotStagingBytes() && stagedBytes + rootMetadata <= bounds.maxRetainedLogBytes(),
                CAPACITY_EXCEEDED, "generation exceeds retained/staging bounds before writing");
        var selected = selected(root, manifest, node, bounds);
        String name = selected.directory().getFileName().toString().equals("generation-a") ? "generation-b" : "generation-a";
        Path target = root.resolve(name);
        if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            require(selected.snapshot() == null || selected.snapshot().index() <= floor(root, manifest, node),
                    CAPACITY_EXCEEDED, "a prior recovery source is retained until its quorum floor is established");
            removeSlot(target, faults);
        }
        require(directoryBytes(root) + stagedBytes + 4096 <= bounds.maxRetainedLogBytes() + bounds.maxSnapshotStagingBytes(),
                CAPACITY_EXCEEDED, "generation would exceed aggregate disk bounds");
        Files.createDirectory(target); forceDirectory(root); faults.at("AFTER_RECOVERY_STAGE_CREATE");
        write(target.resolve(SNAPSHOT), snapshot, faults, "RECOVERY_SNAPSHOT");
        for (String file : List.of(ReplicaStore.ENTRY_FILE, ReplicaStore.PROOF_FILE)) {
            int kind = file.equals(ReplicaStore.ENTRY_FILE) ? ENTRY : PROOF;
            try (var channel = FileChannel.open(target.resolve(file), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
                write(channel, journalHeader(manifest.digest(), node, kind));
                long length = channel.position();
                if (kind == ENTRY) for (var entry : image.entries()) {
                    byte[] bytes = entry.encode(bounds.maxFrameBytes()); length += bytes.length;
                    require(length <= bounds.maxRetainedLogBytes(), CAPACITY_EXCEEDED, "recovery journal exceeds bound"); write(channel, bytes);
                }
                else for (var proof : image.proofs()) {
                    byte[] bytes = proof.encode(); length += bytes.length;
                    require(length <= bounds.maxRetainedLogBytes(), CAPACITY_EXCEEDED, "recovery journal exceeds bound"); write(channel, bytes);
                }
                channel.force(true);
            }
            faults.at("AFTER_RECOVERY_" + (kind == ENTRY ? "ENTRIES" : "PROOFS") + "_FORCE");
        }
        UUID generation = UUID.randomUUID();
        byte[] seal = frame(SEAL_KIND, body(out -> {
            hash(out, manifest.digest()); text(out, node.value()); uuid(out, generation); hash(out, frameDigest(snapshot));
            hash(out, frameDigest(journalHeader(manifest.digest(), node, ENTRY)));
            hash(out, frameDigest(journalHeader(manifest.digest(), node, PROOF)));
        }), MAX_METADATA_BYTES);
        write(target.resolve(SEAL), seal, faults, "RECOVERY_SEAL"); forceDirectory(target);
        long staged = directoryBytes(target);
        require(staged <= bounds.maxSnapshotStagingBytes() && staged <= bounds.maxRetainedLogBytes(), CAPACITY_EXCEEDED, "staged generation exceeds byte bounds");
        faults.at("AFTER_RECOVERY_STAGE_FORCE");
        byte[] pointer = frame(POINTER_KIND, body(out -> {
            hash(out, manifest.digest()); text(out, node.value()); text(out, name); uuid(out, generation); hash(out, frameDigest(seal)); out.writeBoolean(admitted);
        }), MAX_METADATA_BYTES);
        atomic(root, CURRENT, PENDING, pointer, faults, "RECOVERY_POINTER");
        ensureStarted(root, manifest, node);
        return selected(root, manifest, node, bounds);
    }

    static void ensureStarted(Path root, ReplicaManifest manifest, ReplicationNodeId node) throws IOException {
        if (!Files.exists(root.resolve(STARTED), LinkOption.NOFOLLOW_LINKS)) {
            write(root.resolve(STARTED), frame(15, body(out -> { hash(out, manifest.digest()); text(out, node.value()); }), MAX_METADATA_BYTES), ReplicaStore.Faults.NONE, "GENERATION_STARTED");
            forceDirectory(root);
        }
    }

    static void validateFloor(Path root, ReplicaManifest manifest, ReplicationNodeId node, ReplicaSnapshot snapshot) throws IOException {
        long floor = floor(root, manifest, node);
        if (Files.exists(root.resolve(FLOOR), LinkOption.NOFOLLOW_LINKS)) {
            var in = input(read(root.resolve(FLOOR), FLOOR_KIND, MAX_METADATA_BYTES)); hash(in); text(in, 64); in.readLong();
            require(snapshot != null && floor <= snapshot.index() && hash(in).equals(snapshot.digestAt(floor)), INTEGRITY_FAILURE, "floor ancestry differs from installed snapshot");
        }
    }

    static long floor(Path root, ReplicaManifest manifest, ReplicationNodeId node) throws IOException {
        if (!Files.exists(root.resolve(FLOOR), LinkOption.NOFOLLOW_LINKS)) return 0;
        var in = input(read(root.resolve(FLOOR), FLOOR_KIND, MAX_METADATA_BYTES));
        require(hash(in).equals(manifest.digest()) && text(in, 64).equals(node.value()), PROTOCOL_MISMATCH, "floor identity mismatch");
        long index = in.readLong(); hash(in); int count = in.readInt();
        require(index >= 0 && index <= MAX_ENTRIES && count >= 2 && count <= 3, INTEGRITY_FAILURE, "invalid recovery floor");
        String previous = "";
        for (int i = 0; i < count; i++) { String voter = text(in, 64); require(manifest.members().stream().anyMatch(m -> m.nodeId().value().equals(voter)) && previous.compareTo(voter) < 0, INTEGRITY_FAILURE, "invalid floor voters"); previous = voter; }
        end(in); return index;
    }
    static void advanceFloor(Path root, ReplicaManifest manifest, ReplicationNodeId node, ReplicaSnapshot snapshot,
                             long index, String digest, List<ReplicationNodeId> voters, ReplicaStore.Faults faults) throws IOException {
        require(snapshot != null && index <= snapshot.index() && index >= floor(root, manifest, node)
                && snapshot.digestAt(index).equals(digest), CONFLICTING_HISTORY, "floor is not covered by installed snapshot");
        require(voters.size() >= 2 && voters.size() <= 3 && voters.stream().distinct().count() == voters.size()
                && voters.stream().allMatch(manifest::contains), INTEGRITY_FAILURE, "floor requires distinct durable recovery voters");
        byte[] record = frame(FLOOR_KIND, body(out -> {
            hash(out, manifest.digest()); text(out, node.value()); out.writeLong(index); hash(out, digest); out.writeInt(voters.size());
            for (var voter : voters.stream().sorted().toList()) text(out, voter.value());
        }), MAX_METADATA_BYTES);
        atomic(root, FLOOR, "recovery-floor.pending.gsr", record, faults, "RECOVERY_FLOOR");
    }
    static void compact(Path root, Selected selected, ReplicaManifest manifest, ReplicationNodeId node,
                        ReplicaStore.Faults faults) throws IOException {
        require(selected.snapshot() != null && selected.snapshot().index() <= floor(root, manifest, node), CONFLICTING_HISTORY, "compaction requires quorum recovery floor");
        for (String slot : SLOTS) if (!root.resolve(slot).equals(selected.directory()) && Files.exists(root.resolve(slot), LinkOption.NOFOLLOW_LINKS)) removeSlot(root.resolve(slot), faults);
        // Original journal headers remain part of the immutable initialization inventory.
        for (String file : List.of(ReplicaStore.ENTRY_FILE, ReplicaStore.PROOF_FILE)) {
            try (var channel = FileChannel.open(root.resolve(file), StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
                channel.truncate(journalHeader(manifest.digest(), node, file.equals(ReplicaStore.ENTRY_FILE) ? ENTRY : PROOF).length); channel.force(true);
            }
            faults.at("AFTER_RECOVERY_LEGACY_COMPACTION");
        }
        forceDirectory(root); faults.at("AFTER_RECOVERY_CLEANUP_FORCE");
    }
    static byte[] rebuilding(ReplicaManifest manifest, ReplicationNodeId node) {
        return frame(REBUILD_KIND, body(out -> { hash(out, manifest.digest()); text(out, node.value()); }), MAX_METADATA_BYTES);
    }
    static void validateRebuilding(Path root, ReplicaManifest manifest, ReplicationNodeId node) throws IOException {
        if (!Files.exists(root.resolve(REBUILDING), LinkOption.NOFOLLOW_LINKS)) return;
        var in = input(read(root.resolve(REBUILDING), REBUILD_KIND, MAX_METADATA_BYTES));
        require(hash(in).equals(manifest.digest()) && text(in, 64).equals(node.value()), PROTOCOL_MISMATCH, "replacement identity mismatch"); end(in);
    }
    static byte[] journalHeader(String digest, ReplicationNodeId node, int kind) {
        return frame(JOURNAL, body(out -> { hash(out, digest); text(out, node.value()); out.writeShort(kind); }), MAX_METADATA_BYTES);
    }
    static void inventorySlot(Path path, boolean complete) throws IOException {
        require(Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE, "generation is not a directory");
        var names = new java.util.HashSet<String>();
        try (var files = Files.list(path)) {
            var iterator = files.iterator();
            while (iterator.hasNext()) { Path file = iterator.next(); require(names.size() < MEMBERS.size(), INTEGRITY_FAILURE, "too many generation members"); regular(file); require(MEMBERS.contains(file.getFileName().toString()) && names.add(file.getFileName().toString()), INTEGRITY_FAILURE, "unknown generation member"); }
        }
        require(!complete || names.equals(MEMBERS), INTEGRITY_FAILURE, "incomplete selected generation");
    }
    static void regular(Path path) throws IOException {
        require(Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE, "non-regular recovery member");
        if (Files.getFileStore(path).supportsFileAttributeView("unix")) require(((Number) Files.getAttribute(path, "unix:nlink", LinkOption.NOFOLLOW_LINKS)).longValue() == 1, INTEGRITY_FAILURE, "recovery member has multiple hard links");
    }
    static long directoryBytes(Path path) throws IOException {
        long total = 0;
        try (var members = Files.list(path)) { for (Path member : members.toList()) total = Math.addExact(total, Files.isDirectory(member, LinkOption.NOFOLLOW_LINKS) ? directoryBytes(member) : Files.size(member)); }
        return total;
    }
    private static void removeSlot(Path path, ReplicaStore.Faults faults) throws IOException {
        inventorySlot(path, false);
        for (String name : MEMBERS) { Files.deleteIfExists(path.resolve(name)); faults.at("AFTER_RECOVERY_CLEANUP_MEMBER"); }
        Files.delete(path); forceDirectory(path.getParent());
    }
    static byte[] bytes(Path file, int maximum) throws IOException {
        regular(file); long length = Files.size(file);
        require(length > 0 && length <= maximum, CAPACITY_EXCEEDED, "recovery file exceeds bound");
        try (var in = Files.newInputStream(file, LinkOption.NOFOLLOW_LINKS)) {
            byte[] bytes = in.readNBytes(maximum + 1); require(bytes.length == length, INTEGRITY_FAILURE, "recovery file changed while owned"); return bytes;
        }
    }
    private static byte[] read(Path file, int kind, int maximum) throws IOException { return decodeRecord(bytes(file, maximum), kind, maximum); }
    private static void atomic(Path root, String target, String pending, byte[] bytes, ReplicaStore.Faults faults, String operation) throws IOException {
        Files.deleteIfExists(root.resolve(pending));
        write(root.resolve(pending), bytes, faults, operation);
        faults.at("BEFORE_" + operation + "_PUBLISH");
        Files.move(root.resolve(pending), root.resolve(target), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        faults.at("AFTER_" + operation + "_RENAME"); forceDirectory(root); faults.at("AFTER_" + operation + "_FORCE");
    }
    private static void write(Path file, byte[] bytes, ReplicaStore.Faults faults, String operation) throws IOException {
        try (var channel = FileChannel.open(file, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
            write(channel, bytes); channel.force(true);
        }
        faults.at("AFTER_" + operation + "_FILE_FORCE");
    }
    private static void write(FileChannel channel, byte[] bytes) throws IOException {
        var buffer = ByteBuffer.wrap(bytes); int stalls = 0;
        while (buffer.hasRemaining()) { int count = channel.write(buffer); if (count == 0 && ++stalls > 16) throw new IOException("generation write made no progress"); if (count > 0) stalls = 0; }
    }
    private static void forceDirectory(Path path) throws IOException { try (var channel = FileChannel.open(path, StandardOpenOption.READ)) { channel.force(true); } }
}
