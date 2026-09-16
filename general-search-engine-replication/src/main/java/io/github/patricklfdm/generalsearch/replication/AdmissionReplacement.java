package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionConfiguration.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/** A replacement inherits group provenance and starts at genesis as a durable non-voter. */
final class AdmissionReplacement {
    private AdmissionReplacement() { }
    record Spec(AdmissionPlan original, Map<String, Object> descriptor, List<Member> inventory) {
        byte[] encode() {
            return record(23, out -> { out.writeShort(1); blob(out, original.receipt());
                blob(out, ReplicaJson.encode(descriptor, META)); AdmissionFormat.inventory(out, inventory); });
        }
        String digest() { return frameDigest(encode()); }
        Path operation() { return path(descriptor.get("operation")); }
        Path source() { return path(descriptor.get("source")); }
        Map<String, Object> local() { return object(descriptor.get("configuration")); }
        Path target() { return path(local().get("target")); }
        ReplicationNodeId node() { return new ReplicationNodeId(string(local(), "node")); }
        ReplicationReplacementPlan summary() { return new ReplicationReplacementPlan(operation(), source(), node(), target(),
                original.manifest().digest(), inventoryDigest(inventory), digest()); }
        byte[] row(int phase, String previous) {
            return new AdmissionJournal.Row(digest(), phase, previous, phase, List.of(ZERO, ZERO, ZERO), ZERO).encode();
        }
        static Spec read(byte[] bytes) throws IOException {
            var in = decode(bytes, 23, META); require(in.readUnsignedShort() == 1, PROTOCOL_MISMATCH, "unsupported replacement plan");
            var original = AdmissionPlan.receipt(blob(in, META)); var descriptor = object(ReplicaJson.decode(blob(in, META), META));
            var inventory = AdmissionFormat.inventory(in); end(in);
            keys(descriptor, "operation", "source", "configuration", "manifestDigest", "genesisDigest", "sourceInventoryDigest");
            var result = new Spec(original, descriptor, inventory);
            path(descriptor.get("operation")); path(descriptor.get("source")); validateLocal(result.local(), original.manifest());
            require(string(descriptor, "manifestDigest").equals(original.manifest().digest())
                    && string(descriptor, "genesisDigest").equals(original.manifest().genesisDigest())
                    && string(descriptor, "sourceInventoryDigest").equals(inventoryDigest(inventory)), INTEGRITY_FAILURE, "replacement source identity mismatch");
            return result;
        }
    }

    static ReplicationReplacementPlan plan(ReplicationGroupConfig<?, ?> configuration, Path source, Path operation) {
        return AdmissionBootstrap.guarded(() -> {
            AdmissionPaths.absent(operation); AdmissionPaths.absent(configuration.replicaDirectory());
            try (var owner = AdmissionPaths.own(AdmissionPaths.safe(source).resolve("replica.lock"), false)) {
                return project(configuration, source, operation).summary();
            }
        });
    }

    private static Spec project(ReplicationGroupConfig<?, ?> configuration, Path requestedSource, Path requestedOperation) throws IOException {
        Path source = AdmissionPaths.safe(requestedSource), operation = AdmissionPaths.safe(requestedOperation);
        AdmissionPaths.disjoint(List.of(source, operation, configuration.replicaDirectory(), configuration.materialization().directory()));
        var view = AdmissionNode.read(source, configuration.bounds().maxRetainedLogBytes()); var original = view.plan(); var manifest = original.manifest().group();
        require(configuration.groupId().equals(manifest.groupId()) && configuration.configurationId().equals(manifest.configurationId())
                && configuration.members().equals(manifest.members()) && configuration.configuredLeaderId().equals(manifest.leader()),
                PROTOCOL_MISMATCH, "replacement configuration differs from group");
        var local = AdmissionConfiguration.local(configuration); validateLocal(local, original.manifest());
        int index = manifest.members().stream().map(ReplicationMember::nodeId).toList().indexOf(configuration.localNodeId());
        var old = original.local(index);
        require(Arrays.equals(materializationPolicy(local), materializationPolicy(old))
                        && Arrays.equals(ReplicaJson.encode(local.get("replicationBounds"), META), ReplicaJson.encode(old.get("replicationBounds"), META)),
                PROTOCOL_MISMATCH, "replacement must retain the original local configuration and bounds");
        var descriptor = Map.<String, Object>of("operation", AdmissionPaths.binding(operation), "source", AdmissionPaths.binding(source),
                "configuration", local, "manifestDigest", original.manifest().digest(), "genesisDigest", original.manifest().genesisDigest(),
                "sourceInventoryDigest", inventoryDigest(view.inventory()));
        var spec = new Spec(original, descriptor, view.inventory()); spec.encode();
        var files = files(spec, view.genesis());
        long total = files.values().stream().mapToLong(bytes -> bytes.length).reduce(0, Math::addExact);
        total = Math.addExact(total, spec.encode().length + spec.row(1, ZERO).length + 2L * spec.row(2, frameDigest(spec.row(1, ZERO))).length);
        require(total <= configuration.bounds().maxRetainedLogBytes() && view.genesis().length <= Math.min(IMAGE, configuration.bounds().maxSnapshotStagingBytes()),
                CAPACITY_EXCEEDED, "replacement exceeds retained/staging bound");
        return spec;
    }

    private static byte[] materializationPolicy(Map<String, Object> local) {
        var policy = new TreeMap<>(object(local.get("materialization")));
        // A replacement disk has a new filesystem identity at the configured path.
        // Bind that identity in the new plan; apply/resume still reproject it exactly.
        policy.put("directory", path(policy.get("directory")).toString());
        return ReplicaJson.encode(policy, META);
    }

    private static Map<String, byte[]> files(Spec spec, byte[] genesis) {
        var files = payloads(spec.original().manifest(), genesis, spec.node(), true);
        int index = spec.original().manifest().group().members().stream().map(ReplicationMember::nodeId).toList().indexOf(spec.node());
        files.put("bootstrap-prepared.gsr", spec.original().preparation(index)); files.put("bootstrap-seal.gsr", spec.original().seal(index));
        return files;
    }

    static void apply(ReplicationGroupConfig<?, ?> configuration, ReplicationReplacementPlan summary, boolean resume) {
        AdmissionBootstrap.guarded(() -> {
            Path source = AdmissionPaths.safe(summary.sourceReplicaDirectory()), operation = AdmissionPaths.safe(summary.operationDirectory());
            try (var sourceOwner = AdmissionPaths.own(source.resolve("replica.lock"), false)) {
                var projected = project(configuration, source, operation);
                require(projected.summary().equals(summary), CONFLICTING_HISTORY, "replacement plan is stale or forged");
                if (!resume) {
                    AdmissionPaths.absent(operation); AdmissionPaths.absent(projected.target()); Files.createDirectory(operation);
                    AdmissionPaths.forceDirectory(operation.getParent());
                }
                try (var owner = AdmissionPaths.own(operation.resolve("operation.lock"), !resume)) {
                    if (!resume) {
                        AdmissionPaths.write(operation.resolve("replacement-plan.gsr"), projected.encode()); AdmissionIo.at("REPLACEMENT_PLAN_FORCED");
                    } else AdmissionPaths.exact(operation.resolve("replacement-plan.gsr"), projected.encode());
                    Set<String> names = Set.of("operation.lock", "replacement-plan.gsr", "replacement.gsr", "replacement.pending.gsr");
                    for (var member : AdmissionPaths.inventory(operation, 8L * META)) require(member.kind() == 1 && names.contains(member.name()), INTEGRITY_FAILURE, "unknown replacement coordinator member");
                    Path journal = operation.resolve("replacement.gsr"); byte[] first = projected.row(1, ZERO), second = projected.row(2, frameDigest(first));
                    if (!Files.exists(journal, LinkOption.NOFOLLOW_LINKS)) {
                        AdmissionPaths.absent(projected.target()); AdmissionPaths.write(journal, first); AdmissionIo.at("REPLACEMENT_PREPARING_FORCED");
                    }
                    byte[] rows = AdmissionPaths.read(journal, 2 * META);
                    boolean prepared = Arrays.equals(rows, join(first, second));
                    require(prepared || Arrays.equals(rows, first), INTEGRITY_FAILURE, "replacement journal conflicts or is torn");
                    var view = AdmissionNode.read(source, configuration.bounds().maxRetainedLogBytes());
                    require(view.inventory().equals(projected.inventory()), CONFLICTING_HISTORY, "replacement source changed");
                    var expected = files(projected, view.genesis()); Path target = projected.target();
                    boolean created = !Files.exists(target, LinkOption.NOFOLLOW_LINKS);
                    require(!created || !prepared, INTEGRITY_FAILURE, "prepared replacement authority was lost");
                    if (created) { Files.createDirectory(target); AdmissionPaths.forceDirectory(target.getParent()); }
                    boolean createLock = !Files.exists(target.resolve("replica.lock"), LinkOption.NOFOLLOW_LINKS);
                    require(!createLock || !prepared, INTEGRITY_FAILURE, "prepared replacement ownership was lost");
                    try (var targetOwner = AdmissionPaths.own(target.resolve("replica.lock"), createLock)) {
                        AdmissionIo.at("REPLACEMENT_TARGET_CREATED");
                        for (var member : AdmissionPaths.inventory(target, configuration.bounds().maxRetainedLogBytes())) {
                            require(member.kind() == 1 && expected.containsKey(member.name()), INTEGRITY_FAILURE, "unknown replacement target member");
                            byte[] bytes = AdmissionPaths.read(target.resolve(member.name()), expected.get(member.name()).length);
                            require((!prepared || bytes.length == expected.get(member.name()).length)
                                    && Arrays.equals(bytes, Arrays.copyOf(expected.get(member.name()), bytes.length)), CONFLICTING_HISTORY, "replacement target changed");
                        }
                        // The durable rebuilding marker is written before the origin-1 node or completion seal.
                        AdmissionBootstrap.completeFile(target.resolve("rebuilding.gsr"), expected.get("rebuilding.gsr"), !prepared);
                        for (var file : expected.entrySet()) {
                            AdmissionBootstrap.completeFile(target.resolve(file.getKey()), file.getValue(), !prepared);
                            AdmissionIo.at("REPLACEMENT_" + file.getKey() + "_FORCED");
                        }
                        AdmissionNode.read(target, configuration.bounds().maxRetainedLogBytes()); AdmissionIo.at("REPLACEMENT_TARGET_VERIFIED");
                        require(view.inventory().equals(AdmissionPaths.inventory(source, configuration.bounds().maxRetainedLogBytes())), CONFLICTING_HISTORY, "replacement source changed before preparation completion");
                        if (!prepared) {
                            Path pending = operation.resolve("replacement.pending.gsr");
                            AdmissionBootstrap.completeFile(pending, second, true); AdmissionIo.at("REPLACEMENT_ROW_PENDING_FORCED");
                            try (var channel = FileChannel.open(journal, StandardOpenOption.WRITE, StandardOpenOption.APPEND, LinkOption.NOFOLLOW_LINKS)) {
                                AdmissionPaths.write(channel, second); channel.force(true);
                            }
                            AdmissionPaths.forceDirectory(operation); AdmissionIo.at("REPLACEMENT_PREPARED_FORCED");
                        }
                        Path pending = operation.resolve("replacement.pending.gsr");
                        if (Files.exists(pending, LinkOption.NOFOLLOW_LINKS)) { AdmissionPaths.exact(pending, second); Files.delete(pending); AdmissionPaths.forceDirectory(operation); }
                    }
                }
            }
            return null;
        });
    }
}
