package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;

import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Verifies existing sealed authority. This class never creates or repairs a voter. */
final class AutomaticAdmission {
    static final Set<String> INITIAL = Set.of("replica.lock", "manifest.gsr", "genesis.gsr", "node.gsr",
            "promises.gsr", "accepted.gsr", "proofs.gsr", "storage-ready.gsr");
    static final Set<String> ROOT_FILES;
    static { var files = new HashSet<>(INITIAL); files.addAll(List.of("bootstrap-prepared.gsr", "bootstrap-seal.gsr")); ROOT_FILES = Set.copyOf(files); }
    private AutomaticAdmission() { }

    static void checkPlan(Map<String, Object> value) {
        var manifest = decode(unbase(value.get("manifest")), "MANIFEST");
        var genesis = decode(unbase(value.get("genesis")), "GENESIS");
        need(manifest.value().get("genesisDigest").equals(genesis.digest()), "plan genesis hash");
        for (String key : List.of("groupId", "historyId", "baseSequence", "schemaDigest", "indexesDigest"))
            need(manifest.value().get(key).equals(genesis.value().get(key)), "genesis identity: " + key);
        need((value.get("sourcePath") == null) == genesis.value().get("source").equals("EMPTY"), "bootstrap source");
        need((genesis.value().get("sourceDigest") == null) == genesis.value().get("source").equals("EMPTY"), "genesis source digest");
        capacity(number(value, "maxSourceBytes") <= 1L << 40 && number(value, "maxOperationBytes") <= 1L << 40, "bootstrap byte ceilings");
        var targets = list(value.get("targets"));
        need(targets.stream().map(x -> text(object(x), "node")).toList().equals(nodes(manifest.value())), "bootstrap target order");
        var paths = new java.util.ArrayList<Path>(); paths.add(absolute(text(value, "operationPath")));
        if (value.get("sourcePath") != null) paths.add(absolute(text(value, "sourcePath")));
        for (Object item : targets) {
            var target = object(item); paths.add(absolute(text(target, "authorityPath"))); paths.add(absolute(text(target, "materializationPath")));
            var files = list(target.get("files")); var names = files.stream().map(x -> text(object(x), "path")).toList();
            need(names.equals(names.stream().sorted().distinct().toList()), "ordered initial inventory");
            var b = object(target.get("bounds")); var p = object(target.get("policy"));
            try {
                new ReplicationBounds(intValue(b, "maxFrameBytes"), intValue(b, "maxEntriesPerAppend"), intValue(b, "maxInFlightPerPeer"),
                        intValue(b, "maxPendingClientOperations"), intValue(b, "maxRetryAttempts"), intValue(b, "requestTimeoutMillis"),
                        intValue(b, "retryBackoffMillis"), intValue(b, "snapshotChunkBytes"), number(b, "maxRetainedLogBytes"), number(b, "maxSnapshotStagingBytes"));
                new AutomaticLeadershipPolicy(intValue(p, "heartbeatIntervalMillis"), intValue(p, "minElectionTimeoutMillis"),
                        intValue(p, "maxElectionTimeoutMillis"), intValue(p, "operationTimeoutMillis"));
            } catch (IllegalArgumentException | ArithmeticException error) { throw failure(AutomaticReplicationException.Reason.INTEGRITY_FAILURE, "plan bounds/policy", error); }
            need(number(b, "maxFrameBytes") >= 131072 && number(b, "maxInFlightPerPeer") >= 2 && number(b, "snapshotChunkBytes") >= 4096,
                    "automatic control bounds");
            need(number(p, "heartbeatIntervalMillis") >= number(b, "requestTimeoutMillis")
                    && number(p, "operationTimeoutMillis") >= 2 * number(b, "requestTimeoutMillis"), "policy request bound");
        }
        for (int i = 0; i < paths.size(); i++) for (int j = i + 1; j < paths.size(); j++)
            need(!paths.get(i).startsWith(paths.get(j)) && !paths.get(j).startsWith(paths.get(i)), "overlapping bootstrap paths");
    }
    private static int intValue(Map<String, Object> value, String key) { return Math.toIntExact(number(value, key)); }
    private static Path absolute(String path) {
        Path p = Path.of(path); need(p.isAbsolute() && p.normalize().toString().equals(path), "canonical absolute bootstrap path"); return p;
    }
    static void checkReceipt(Map<String, Object> value) {
        var plan = decode(unbase(value.get("plan")), "PLAN");
        var manifest = decode(unbase(plan.value().get("manifest")), "MANIFEST");
        var preparations = list(value.get("preparations")); var targets = list(plan.value().get("targets"));
        for (int i = 0; i < 3; i++) {
            var prep = decode(unbase(preparations.get(i)), "PREPARED"); var target = object(targets.get(i));
            need(prep.value().get("node").equals(target.get("node")) && prep.value().get("planDigest").equals(plan.digest())
                    && prep.value().get("manifestDigest").equals(manifest.digest()), "receipt binding/order");
            // Fixture projections need not describe a bootable inventory; admission checks completeness below.
        }
    }

    static Record verify(Path root, Record expected, String node, ReplicationBounds bounds) throws IOException {
        AutomaticRecoveryFiles.inventory(root, bounds);
        for (String name : ROOT_FILES) need(Files.isRegularFile(root.resolve(name), LinkOption.NOFOLLOW_LINKS), "missing sealed authority file");
        var manifest = decode(read(root.resolve("manifest.gsr"), META), "MANIFEST");
        need(manifest.digest().equals(expected.digest()) && nodes(manifest.value()).contains(node), "expected manifest/voter mismatch");
        var local = decode(read(root.resolve("node.gsr"), META), "NODE"); context(local, manifest);
        need(local.value().get("node").equals(node), "local voter mismatch");
        var ready = decode(read(root.resolve("storage-ready.gsr"), META), "READY"); context(ready, manifest);
        need(ready.value().get("node").equals(node) && ready.value().get("genesisDigest").equals(manifest.value().get("genesisDigest")), "ready identity");
        var seal = decode(read(root.resolve("bootstrap-seal.gsr"), META), "SEAL");
        need(seal.value().get("node").equals(node), "seal identity");
        var receipt = decode(unbase(seal.value().get("receipt")), "RECEIPT");
        var plan = decode(unbase(receipt.value().get("plan")), "PLAN");
        need(java.util.Arrays.equals(unbase(plan.value().get("manifest")), manifest.bytes()), "sealed manifest mismatch");
        need(java.util.Arrays.equals(unbase(plan.value().get("genesis")), read(root.resolve("genesis.gsr"), IMAGE)), "sealed genesis mismatch");
        int ordinal = nodes(manifest.value()).indexOf(node);
        var target = object(list(plan.value().get("targets")).get(ordinal));
        need(root.toString().equals(target.get("authorityPath")), "copied/stale seal path");
        var sealedBounds = object(target.get("bounds"));
        need(bounds.maxFrameBytes() <= number(sealedBounds, "maxFrameBytes")
                && bounds.maxRetainedLogBytes() <= number(sealedBounds, "maxRetainedLogBytes")
                && bounds.maxSnapshotStagingBytes() <= number(sealedBounds, "maxSnapshotStagingBytes"), "store bounds exceed sealed authority limits");
        var prep = decode(read(root.resolve("bootstrap-prepared.gsr"), META), "PREPARED");
        need(java.util.Arrays.equals(prep.bytes(), unbase(list(receipt.value().get("preparations")).get(ordinal))), "local preparation mismatch");
        for (int i = 0; i < 3; i++) {
            var voterTarget = object(list(plan.value().get("targets")).get(i));
            var prepared = decode(unbase(list(receipt.value().get("preparations")).get(i)), "PREPARED");
            need(prepared.value().get("inventoryDigest").equals(sha(canonical(voterTarget.get("files")))), "preparation inventory binding");
            need(initial(list(voterTarget.get("files")).stream().map(v -> text(object(v), "path")).toList()), "complete preparation inventory");
        }
        var inventory = list(target.get("files"));
        need(initial(inventory.stream().map(x -> text(object(x), "path")).toList()), "initial inventory completeness");
        for (Object item : inventory) {
            var file = object(item); String name = text(file, "path"); long size = number(file, "size");
            capacity(size <= IMAGE && size <= bounds.maxRetainedLogBytes(), "initial file size");
            boolean ledger = Set.of("promises.gsr", "accepted.gsr", "proofs.gsr").contains(name);
            need(ledger ? Files.size(root.resolve(name)) >= size : Files.size(root.resolve(name)) == size, "missing/changed initial authority");
            try (var in = FileChannel.open(root.resolve(name), StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
                var prefix = ByteBuffer.allocate((int) size); readFully(in, prefix);
                need(sha(prefix.array()).equals(file.get("sha256")), "initial authority hash");
            }
        }
        need(Files.size(root.resolve("replica.lock")) == 0, "unexpected ownership bytes");
        if (Files.exists(root.resolve(AutomaticBootstrapPlan.BINDING),LinkOption.NOFOLLOW_LINKS)) {
            var bound = new AutomaticBootstrapPlan(plan,read(root.resolve(AutomaticBootstrapPlan.BINDING),META));
            // Startup depends only on the local sealed binding, never on coordinator/source availability.
            var localBinding = object(list(bound.descriptor().get("replicas")).get(ordinal));
            AdmissionPaths.recheck(object(localBinding.get("target")));
        }
        return manifest;
    }
    private static boolean initial(List<String> names) {
        var extended = new java.util.TreeSet<>(INITIAL); extended.add(AutomaticBootstrapPlan.BINDING);
        return names.equals(INITIAL.stream().sorted().toList()) || names.equals(List.copyOf(extended));
    }
    static Path safe(Path path) throws IOException {
        Path p = path.toAbsolutePath().normalize();
        for (Path at = p; at != null; at = at.getParent()) need(!Files.isSymbolicLink(at), "symlink authority path");
        need(Files.isDirectory(p, LinkOption.NOFOLLOW_LINKS) && p.toRealPath().equals(p), "absent/noncanonical authority directory");
        String type = Files.getFileStore(p).type().toLowerCase(java.util.Locale.ROOT);
        if (List.of("nfs", "cifs", "smb", "fuse", "tmpfs", "ramfs", "9p").stream().anyMatch(type::contains))
            throw failure(AutomaticReplicationException.Reason.STORAGE_FAILURE, "unsupported automatic authority filesystem: " + type, null);
        return p;
    }
    static byte[] read(Path path, int maximum) throws IOException {
        need(Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS), "missing/nonregular authority file");
        try (var in = FileChannel.open(path, StandardOpenOption.READ, LinkOption.NOFOLLOW_LINKS)) {
            capacity(in.size() <= maximum, "authority file byte bound");
            var bytes = ByteBuffer.allocate((int) in.size()); readFully(in, bytes); return bytes.array();
        }
    }
    static void readFully(FileChannel channel, ByteBuffer bytes) throws IOException {
        int stalls = 0;
        while (bytes.hasRemaining()) {
            int read = channel.read(bytes); if (read < 0 || (read == 0 && ++stalls > 16)) throw new IOException("authority read made no progress");
        }
    }
}
