package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Set;
import java.util.UUID;

/** One bounded incoming image. The transfer is never selected replica authority. */
final class ReplicaTransfer {
    static final String DIRECTORY = "transfer", OFFER = "offer.gsr", DATA = "image.bin";
    private static final int KIND = 14;
    private final Path directory;
    private final ReplicaManifest manifest;
    private final ReplicationNodeId local;
    private final ReplicationBounds bounds;
    private UUID id;
    private long length;
    private String digest;
    ReplicaTransfer(Path root, ReplicaManifest manifest, ReplicationNodeId local, ReplicationBounds bounds) {
        directory = root.resolve(DIRECTORY); this.manifest = manifest; this.local = local; this.bounds = bounds;
    }
    static int chunkSize(ReplicationBounds bounds) { return Math.min(bounds.snapshotChunkBytes(), (bounds.maxFrameBytes() - 2048) / 4 * 3); }
    void begin(UUID id, long length, String digest) throws IOException {
        validHash(digest);
        require(length > 0 && length <= ReplicaSnapshot.maximum(bounds)
                && (length + chunkSize(bounds) - 1) / chunkSize(bounds) <= 100_000, CAPACITY_EXCEEDED, "snapshot transfer exceeds bounds");
        if (id.equals(this.id)) { require(this.length == length && this.digest.equals(digest), CONFLICTING_HISTORY, "conflicting transfer retry"); return; }
        byte[] offer = frame(KIND, body(out -> {
            hash(out, manifest.digest()); text(out, local.value()); uuid(out, id); out.writeLong(length); hash(out, digest);
        }), MAX_METADATA_BYTES);
        require(length + offer.length <= bounds.maxSnapshotStagingBytes(), CAPACITY_EXCEEDED, "transfer metadata exceeds staging bound");
        abort();
        require(ReplicaGeneration.directoryBytes(directory.getParent()) + length + offer.length + 4096
                        <= bounds.maxRetainedLogBytes() + bounds.maxSnapshotStagingBytes(),
                CAPACITY_EXCEEDED, "transfer would exceed aggregate disk bounds");
        Files.createDirectory(directory);
        try (var channel = FileChannel.open(directory.resolve(OFFER), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
            write(channel, ByteBuffer.wrap(offer)); channel.force(true);
        }
        try (var channel = FileChannel.open(directory.resolve(DATA), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) { channel.force(true); }
        force(directory); force(directory.getParent()); this.id = id; this.length = length; this.digest = digest;
    }
    long chunk(UUID id, long offset, byte[] bytes) throws IOException {
        require(id.equals(this.id), CONFLICTING_HISTORY, "snapshot transfer is not active");
        require(offset >= 0 && bytes.length > 0 && bytes.length <= chunkSize(bounds) && offset <= length - bytes.length,
                CAPACITY_EXCEEDED, "snapshot chunk exceeds bounds");
        try (var channel = FileChannel.open(directory.resolve(DATA), StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
            long size = channel.size();
            if (offset < size) {
                require(offset + bytes.length <= size, CONFLICTING_HISTORY, "overlapping partial chunk retry");
                var previous = ByteBuffer.allocate(bytes.length);
                while (previous.hasRemaining()) require(channel.read(previous, offset + previous.position()) > 0, INTEGRITY_FAILURE, "incomplete chunk retry");
                require(java.util.Arrays.equals(previous.array(), bytes), CONFLICTING_HISTORY, "conflicting snapshot chunk retry");
            } else {
                require(offset == size, CONFLICTING_HISTORY, "snapshot chunks must be contiguous");
                channel.position(offset); write(channel, ByteBuffer.wrap(bytes));
            }
            channel.force(true); return offset + bytes.length;
        }
    }
    byte[] complete(UUID id) throws IOException {
        require(id.equals(this.id), CONFLICTING_HISTORY, "snapshot transfer is not active");
        require(Files.size(directory.resolve(DATA)) == length, INTEGRITY_FAILURE, "snapshot transfer is incomplete");
        byte[] bytes = ReplicaGeneration.bytes(directory.resolve(DATA), ReplicaSnapshot.maximum(bounds));
        require(sha256(bytes).equals(digest), INTEGRITY_FAILURE, "snapshot transfer checksum mismatch"); return bytes;
    }
    void abort() throws IOException {
        if (Files.exists(directory, LinkOption.NOFOLLOW_LINKS)) {
            inventory(directory);
            Files.deleteIfExists(directory.resolve(DATA)); Files.deleteIfExists(directory.resolve(OFFER)); Files.delete(directory); force(directory.getParent());
        }
        id = null;
    }
    static void inventory(Path directory) throws IOException {
        require(Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE, "transfer staging is not a directory");
        try (var files = Files.list(directory)) {
            var iterator = files.iterator(); int count = 0;
            while (iterator.hasNext()) { Path file = iterator.next(); require(++count <= 2 && Set.of(OFFER, DATA).contains(file.getFileName().toString()), INTEGRITY_FAILURE, "unknown transfer staging member"); ReplicaGeneration.regular(file); }
        }
    }
    private static void write(FileChannel channel, ByteBuffer bytes) throws IOException {
        int stalls = 0;
        while (bytes.hasRemaining()) { int count = channel.write(bytes); if (count == 0 && ++stalls > 16) throw new IOException("snapshot staging made no progress"); if (count > 0) stalls = 0; }
    }
    private static void force(Path directory) throws IOException { try (var channel = FileChannel.open(directory, StandardOpenOption.READ)) { channel.force(true); } }
}
