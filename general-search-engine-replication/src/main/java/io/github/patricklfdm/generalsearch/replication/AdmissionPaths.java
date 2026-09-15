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
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/** Filesystem bindings and exclusive owners shared by synchronous offline operations. */
final class AdmissionPaths {
    private AdmissionPaths() { }

    static Path safe(Path requested) {
        Path path = requested.toAbsolutePath().normalize();
        require(path.getParent() != null, STORAGE_FAILURE, "authority cannot be a filesystem root");
        for (Path part = path; part != null; part = part.getParent()) {
            require(!Files.isSymbolicLink(part), STORAGE_FAILURE, "symlink in authority path");
        }
        return path;
    }

    static Map<String, Object> binding(Path requested) throws IOException {
        Path path = safe(requested), parent = path.getParent();
        require(Files.isDirectory(parent, LinkOption.NOFOLLOW_LINKS), STORAGE_FAILURE, "parent must already exist");
        var attributes = Files.readAttributes(parent, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        var store = Files.getFileStore(parent);
        String type = store.type().toLowerCase(Locale.ROOT);
        require(List.of("nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p")
                        .stream().noneMatch(type::contains), STORAGE_FAILURE, "unsupported authority filesystem");
        require(attributes.fileKey() != null && !store.name().isBlank() && !store.type().isBlank(),
                STORAGE_FAILURE, "stable filesystem identity unavailable");
        var result = Map.<String, Object>of("path", path.toString(), "parentRealPath", parent.toRealPath().toString(),
                "fileStoreName", store.name(), "fileStoreType", store.type(), "parentFileKey", attributes.fileKey().toString());
        for (var value : result.values()) require(((String) value).getBytes(java.nio.charset.StandardCharsets.UTF_8).length <= 4096,
                CAPACITY_EXCEEDED, "path binding exceeds bound");
        require(parent.equals(parent.toRealPath()), STORAGE_FAILURE, "aliased authority parent");
        return result;
    }

    static void recheck(Map<String, Object> bound) throws IOException {
        require(bound.equals(binding(Path.of((String) bound.get("path")))), CONFLICTING_HISTORY, "path identity changed");
    }

    static void disjoint(List<Path> paths) throws IOException {
        for (int i = 0; i < paths.size(); i++) {
            Path a = safe(paths.get(i));
            for (int j = 0; j < i; j++) {
                Path b = safe(paths.get(j));
                require(!a.startsWith(b) && !b.startsWith(a)
                                && !(Files.exists(a, LinkOption.NOFOLLOW_LINKS) && Files.exists(b, LinkOption.NOFOLLOW_LINKS)
                                && Files.isSameFile(a, b)), STORAGE_FAILURE, "overlapping authority/source paths");
            }
        }
    }

    static void absent(Path path) {
        require(!Files.exists(safe(path), LinkOption.NOFOLLOW_LINKS), STORAGE_FAILURE, "target must be absent: " + path);
    }

    static void regular(Path path) throws IOException {
        safe(path);
        require(Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)
                        && ((Number) Files.getAttribute(path, "unix:nlink", LinkOption.NOFOLLOW_LINKS)).longValue() == 1,
                STORAGE_FAILURE, "authority member is not a single regular file: " + path);
    }

    static byte[] read(Path path, int maximum) throws IOException {
        regular(path);
        try (var channel = FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            long size = channel.size();
            require(size <= maximum, CAPACITY_EXCEEDED, "authority member exceeds bound");
            var buffer = ByteBuffer.allocate(Math.toIntExact(size));
            while (buffer.hasRemaining()) require(channel.read(buffer) > 0, INTEGRITY_FAILURE, "member changed while reading");
            require(channel.size() == size, INTEGRITY_FAILURE, "member grew while reading");
            return buffer.array();
        }
    }

    static List<AdmissionFormat.Member> inventory(Path directory, long maximum) throws IOException {
        safe(directory);
        require(Files.isDirectory(directory, LinkOption.NOFOLLOW_LINKS), STORAGE_FAILURE, "authority directory is absent");
        var result = new ArrayList<AdmissionFormat.Member>();
        long total = 0;
        try (var paths = Files.walk(directory)) {
            var iterator = paths.iterator(); iterator.next();
            while (iterator.hasNext()) {
                Path path = iterator.next();
                require(result.size() < 10_000, CAPACITY_EXCEEDED, "inventory count exceeds bound");
                String name = directory.relativize(path).toString();
                safe(path);
                if (Files.isDirectory(path, LinkOption.NOFOLLOW_LINKS)) {
                    result.add(new AdmissionFormat.Member(name, 0, 0, AdmissionFormat.ZERO));
                    continue;
                }
                regular(path);
                long size = Files.size(path); total = Math.addExact(total, size);
                require(total <= maximum, CAPACITY_EXCEEDED, "inventory exceeds retained bytes");
                result.add(new AdmissionFormat.Member(name, 1, size, digest(path, size)));
            }
        }
        result.sort(java.util.Comparator.comparing(AdmissionFormat.Member::name, AdmissionFormat.UTF8));
        return List.copyOf(result);
    }

    private static String digest(Path path, long size) throws IOException {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            try (var channel = FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
                var buffer = ByteBuffer.allocate(64 * 1024); long read = 0;
                int count;
                while ((count = channel.read(buffer)) > 0) {
                    read = Math.addExact(read, count); require(read <= size, INTEGRITY_FAILURE, "inventory member grew");
                    buffer.flip(); digest.update(buffer); buffer.clear();
                }
                require(read == size, INTEGRITY_FAILURE, "inventory member changed");
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException impossible) { throw new AssertionError(impossible); }
    }

    static void forceDirectory(Path directory) throws IOException {
        try (var channel = FileChannel.open(directory, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) { channel.force(true); }
    }

    static void write(Path path, byte[] bytes) throws IOException {
        try (var channel = FileChannel.open(path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
            write(channel, bytes); channel.force(true);
        }
        forceDirectory(path.getParent());
    }

    static void write(FileChannel channel, byte[] bytes) throws IOException {
        var buffer = ByteBuffer.wrap(bytes);
        while (buffer.hasRemaining()) require(channel.write(buffer) > 0, STORAGE_FAILURE, "authority write stalled");
    }

    static void exact(Path path, byte[] bytes) throws IOException {
        require(java.util.Arrays.equals(read(path, bytes.length), bytes), CONFLICTING_HISTORY, "existing member differs from exact plan: " + path);
    }

    static void publish(Path pending, Path target, byte[] bytes) throws IOException {
        publish(pending, target, bytes, null);
    }

    static void publish(Path pending, Path target, byte[] bytes, String barrier) throws IOException {
        if (Files.exists(target, LinkOption.NOFOLLOW_LINKS)) {
            exact(target, bytes);
        } else {
            AdmissionBootstrap.completeFile(pending, bytes, true);
            try (var channel = FileChannel.open(pending, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) { channel.force(true); }
            if (barrier != null) AdmissionIo.at(barrier + "_PENDING_FORCED");
            absent(target);
            Files.move(pending, target, StandardCopyOption.ATOMIC_MOVE);
            if (barrier != null) AdmissionIo.at(barrier + "_RENAMED");
        }
        try (var channel = FileChannel.open(target, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) { channel.force(true); }
        forceDirectory(target.getParent());
        if (Files.exists(pending, LinkOption.NOFOLLOW_LINKS)) {
            exact(pending, bytes); Files.delete(pending); forceDirectory(target.getParent());
        }
    }

    static Owner own(Path path, boolean create) throws IOException {
        return own(path, create, true);
    }

    static Owner own(Path path, boolean create, boolean empty) throws IOException {
        if (!create) regular(path);
        FileChannel channel = FileChannel.open(path, create
                ? Set.of(StandardOpenOption.CREATE_NEW, StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)
                : Set.of(StandardOpenOption.READ, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS));
        try {
            FileLock lock = channel.tryLock();
            require(lock != null, STORAGE_FAILURE, "offline authority is owned by another process");
            require(!empty || channel.size() == 0, INTEGRITY_FAILURE, "lock file is not empty");
            if (create) { channel.force(true); forceDirectory(path.getParent()); }
            return new Owner(channel, lock);
        } catch (IOException | RuntimeException failure) {
            channel.close();
            if (failure instanceof OverlappingFileLockException) throw failure(STORAGE_FAILURE, "offline authority is already owned", failure);
            throw failure;
        }
    }

    record Owner(FileChannel channel, FileLock lock) implements AutoCloseable {
        @Override public void close() throws IOException { try { lock.close(); } finally { channel.close(); } }
    }
}
