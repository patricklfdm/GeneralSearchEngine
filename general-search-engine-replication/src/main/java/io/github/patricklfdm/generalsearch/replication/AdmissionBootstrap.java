package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionFormat.*;
import static io.github.patricklfdm.generalsearch.replication.AdmissionConfiguration.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;

/** One offline all-three prepare/decision protocol. No node writer or runtime is opened. */
final class AdmissionBootstrap {
    static final Set<String> OPERATION_FILES = Set.of("operation.lock", "plan.gsr", "operation.gsr", "receipt.pending.gsr", "receipt.gsr", "cleanup.gsr");
    private AdmissionBootstrap() { }
    record Projection(AdmissionPlan plan, byte[] genesis, List<Map<String, byte[]>> files) { }

    static <K, T> ReplicationBootstrapPlan plan(SearchEngineBuilder<K, T> builder, ReplicationBootstrapRequest<K, T> request) {
        return guarded(() -> project(builder, request, true).plan().summary());
    }

    static <K, T> Projection project(SearchEngineBuilder<K, T> builder, ReplicationBootstrapRequest<K, T> request, boolean absent) throws IOException {
        var captured = builder.configuration();
        var descriptor = descriptor(captured, request, null);
        var paths = new ArrayList<Path>(); paths.add(request.operationDirectory());
        if (request.sourcePath() != null) paths.add(request.sourcePath());
        for (var local : request.replicas()) { paths.add(local.replicaDirectory()); paths.add(local.materialization().directory()); }
        AdmissionPaths.disjoint(paths);
        if (absent) {
            AdmissionPaths.absent(request.operationDirectory());
            for (var local : request.replicas()) AdmissionPaths.absent(local.replicaDirectory());
        }
        var first = request.replicas().getFirst(); var core = first.materialization();
        Source source; List<T> documents;
        if (request.source() == ReplicationBootstrapSource.EMPTY) {
            source = new Source(0, 0, NO_INCARNATION, 0, List.of()); documents = List.of();
        } else {
            var before = AdmissionPaths.inventory(AdmissionPaths.safe(request.sourcePath()), request.maxSourceBytes());
            var imported = captured.newBuilder().readDurableBackup(request.sourcePath(), new DurableVerificationConfig<>(
                    core.storageIdentity(), core.schemaIdentity(), core.codec(), core.codec().codecVersion(),
                    core.maxEncodedKeyBytes(), core.maxEncodedDocumentBytes(), core.maxDocuments()), request.maxSourceBytes());
            var format = DurableStorageOperations.inspectBackupFormat(request.sourcePath()).declaredFormat().orElseThrow();
            source = new Source(1, format.minor(), imported.history(), imported.sequence(), before); documents = imported.documents();
            require(before.equals(AdmissionPaths.inventory(AdmissionPaths.safe(request.sourcePath()), request.maxSourceBytes())),
                    INTEGRITY_FAILURE, "source changed during typed planning");
        }
        int maximum = IMAGE;
        for (var local : request.replicas()) maximum = (int) Math.min(maximum, local.bounds().maxSnapshotStagingBytes());
        byte[] application = application(captured, documents, core, maximum);
        for (var local : request.replicas()) require(Arrays.equals(application,
                application(captured, documents, local.materialization(), maximum)), PROTOCOL_MISMATCH, "local codecs disagree on canonical genesis");
        var history = history(first.groupId().value());
        var genesis = new Genesis(first.groupId().value(), source, history, source.sequence(), application).encode(maximum);
        var indexDescriptions = captured.indexes().stream().map(ReplicaApplication::descriptor).sorted().toList();
        var base = new ReplicaManifest(first.groupId(), first.configurationId(), first.configuredLeaderId(), first.members(),
                core.codec().codecId(), core.codec().codecVersion(), core.schemaIdentity(), 1, sha256(ReplicaJson.encode(indexDescriptions, META)));
        var manifest = new Manifest(base, frameDigest(genesis), history, source.sequence());
        var files = request.replicas().stream().map(local -> payloads(manifest, genesis, local.localNodeId(), false)).toList();
        var plan = new AdmissionPlan(descriptor, manifest, source, genesis.length, files.stream().map(AdmissionFormat::inventory).toList());
        plan.checkBudget(); return new Projection(plan, genesis, files);
    }

    static <K, T> Map<String, Object> descriptor(SearchEngineConfiguration<K, T> captured,
            ReplicationBootstrapRequest<K, T> request, AdmissionPlan committed) throws IOException {
        var root = new LinkedHashMap<String, Object>();
        root.put("operation", AdmissionPaths.binding(request.operationDirectory()));
        root.put("source", request.sourcePath() == null ? null : committed == null
                ? AdmissionPaths.binding(request.sourcePath()) : committed.descriptor().get("source"));
        if (committed != null) {
            require((request.sourcePath() == null ? null : request.sourcePath().toAbsolutePath().normalize()) == null
                            ? committed.sourcePath() == null : request.sourcePath().toAbsolutePath().normalize().equals(committed.sourcePath()),
                    CONFLICTING_HISTORY, "source request path differs from committed plan");
            require(request.source() == committed.summary().source(), CONFLICTING_HISTORY, "source kind changed");
        }
        root.put("maxSourceBytes", request.maxSourceBytes()); root.put("maxOperationBytes", request.maxOperationBytes());
        root.put("application", AdmissionConfiguration.application(captured));
        var locals = new ArrayList<Map<String, Object>>();
        for (var local : request.replicas()) {
            if (committed != null) require(local.groupId().equals(committed.manifest().group().groupId())
                    && local.configurationId().equals(committed.manifest().group().configurationId())
                    && local.configuredLeaderId().equals(committed.manifest().group().leader())
                    && local.members().equals(committed.manifest().group().members()), PROTOCOL_MISMATCH, "group request changed");
            locals.add(local(local));
        }
        root.put("replicas", locals); return root;
    }

    static <K, T> byte[] application(SearchEngineConfiguration<K, T> config, List<T> documents,
            DurableStorageConfig<K, T> core, int maximum) {
        require(documents.size() <= core.maxDocuments(), CAPACITY_EXCEEDED, "genesis document count exceeds local bound");
        return body(out -> {
            out.writeShort(1); var sorted = config.indexes().stream().sorted(java.util.Comparator.comparing(i -> i.field().name())).toList();
            out.writeInt(sorted.size());
            for (var index : sorted) { text(out, ReplicaApplication.descriptor(index)); require(out.size() <= maximum - 128, CAPACITY_EXCEEDED, "genesis indexes exceed bound"); }
            out.writeInt(documents.size()); var keys = new HashSet<K>();
            for (T document : documents) {
                K key = config.schema().idOf(document);
                require(key != null && keys.add(key), INTEGRITY_FAILURE, "duplicate or null genesis key");
                var codec = core.codec(); byte[] keyBytes = codec.encodeKey(key).clone(), bytes = codec.encodeDocument(document).clone();
                require(keyBytes.length <= core.maxEncodedKeyBytes() && bytes.length <= core.maxEncodedDocumentBytes(), CAPACITY_EXCEEDED, "genesis codec bytes exceed bound");
                require((long) out.size() + 8 + keyBytes.length + bytes.length <= maximum - 128, CAPACITY_EXCEEDED, "genesis application exceeds snapshot bound");
                T decoded = codec.decodeDocument(bytes.clone()); K decodedKey = codec.decodeKey(keyBytes.clone());
                require(key.equals(decodedKey) && key.equals(config.schema().idOf(decoded))
                                && Arrays.equals(keyBytes, codec.encodeKey(decodedKey)) && Arrays.equals(keyBytes, codec.encodeKey(key))
                                && Arrays.equals(bytes, codec.encodeDocument(decoded)) && Arrays.equals(bytes, codec.encodeDocument(document)),
                        INTEGRITY_FAILURE, "noncanonical genesis codec");
                blob(out, keyBytes); blob(out, bytes);
            }
        });
    }

    static <K, T> ReplicationBootstrapResult apply(SearchEngineBuilder<K, T> builder, ReplicationBootstrapRequest<K, T> request,
            ReplicationBootstrapPlan summary, boolean resume) {
        return guarded(() -> {
            Path operation = AdmissionPaths.safe(request.operationDirectory());
            if (!resume) {
                var projection = project(builder, request, true);
                require(projection.plan().summary().equals(summary), CONFLICTING_HISTORY, "caller plan differs from complete projection");
                Files.createDirectory(operation); AdmissionPaths.forceDirectory(operation.getParent());
                try (var owner = AdmissionPaths.own(operation.resolve("operation.lock"), true)) {
                    AdmissionPaths.write(operation.resolve("plan.gsr"), projection.plan().encode()); AdmissionIo.at("BOOTSTRAP_PLAN_FORCED");
                    append(operation, projection.plan().row(1, 1, ZERO)); AdmissionIo.at("BOOTSTRAP_PREPARING_FORCED");
                    return complete(builder, request, projection);
                }
            }
            try (var owner = AdmissionPaths.own(operation.resolve("operation.lock"), false)) {
                operationInventory(operation);
                var plan = AdmissionPlan.read(AdmissionPaths.read(operation.resolve("plan.gsr"), META));
                require(plan.operation().equals(operation) && plan.summary().equals(summary), CONFLICTING_HISTORY, "resume plan differs from retained authority");
                if (!Files.exists(operation.resolve("operation.gsr"), LinkOption.NOFOLLOW_LINKS)) {
                    var projected = project(builder, request, false);
                    require(Arrays.equals(plan.encode(), projected.plan().encode()), CONFLICTING_HISTORY, "source/configuration changed");
                    for (int i = 0; i < 3; i++) AdmissionPaths.absent(plan.target(i));
                    append(operation, plan.row(1, 1, ZERO));
                    return complete(builder, request, projected);
                }
                var tail = AdmissionJournal.read(operation.resolve("operation.gsr"), plan).getLast();
                require(tail.phase() != 5, CONFLICTING_HISTORY, "aborted bootstrap cannot resume");
                Projection projection;
                if (tail.phase() < 3) {
                    projection = project(builder, request, false);
                    require(Arrays.equals(plan.encode(), projection.plan().encode()), CONFLICTING_HISTORY, "source/configuration changed before decision");
                } else {
                    require(Arrays.equals(ReplicaJson.encode(plan.descriptor(), META), ReplicaJson.encode(descriptor(builder.configuration(), request, plan), META)),
                            CONFLICTING_HISTORY, "request differs from committed descriptor");
                    byte[] genesis = AdmissionPaths.read(plan.target(0).resolve("genesis.gsr"), IMAGE); Genesis.read(genesis, plan.manifest());
                    var files = plan.manifest().group().members().stream().map(member -> payloads(plan.manifest(), genesis, member.nodeId(), false)).toList();
                    projection = new Projection(plan, genesis, files);
                }
                return complete(builder, request, projection);
            }
        });
    }

    private static <K, T> ReplicationBootstrapResult complete(SearchEngineBuilder<K, T> builder,
            ReplicationBootstrapRequest<K, T> request, Projection projection) throws IOException {
        var plan = projection.plan(); Path operation = plan.operation(); operationInventory(operation);
        var tail = AdmissionJournal.read(operation.resolve("operation.gsr"), plan).getLast();
        require(!Files.exists(operation.resolve("cleanup.gsr"), LinkOption.NOFOLLOW_LINKS), CONFLICTING_HISTORY,
                "retained cleanup intent forbids bootstrap continuation");
        require(tail.phase() >= 3 || !Files.exists(operation.resolve("receipt.gsr"), LinkOption.NOFOLLOW_LINKS)
                && !Files.exists(operation.resolve("receipt.pending.gsr"), LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE,
                "receipt appears before the durable committing phase");
        var owners = new ArrayList<AdmissionPaths.Owner>();
        try {
            for (int i = 0; i < 3; i++) {
                Path target = plan.target(i); var expected = projection.files().get(i);
                require(inventory(expected).equals(plan.payloads().get(i)), INTEGRITY_FAILURE, "prepared payload projection mismatch");
                AdmissionPaths.recheck(object(plan.local(i).get("target")));
                boolean created = !Files.exists(target, LinkOption.NOFOLLOW_LINKS);
                require(!created || tail.phase() == 1, INTEGRITY_FAILURE, "prepared authority was lost; use disk replacement");
                if (created) { Files.createDirectory(target); AdmissionPaths.forceDirectory(target.getParent()); }
                boolean newLock = !Files.exists(target.resolve("replica.lock"), LinkOption.NOFOLLOW_LINKS);
                require(!newLock || tail.phase() == 1, INTEGRITY_FAILURE, "prepared ownership was lost");
                owners.add(AdmissionPaths.own(target.resolve("replica.lock"), newLock));
                AdmissionIo.at("BOOTSTRAP_TARGET_" + i + "_CREATED");
                verifyPartial(target, expected, plan, i, tail.phase());
            }
            if (tail.phase() == 1) {
                for (int i = 0; i < 3; i++) {
                    Path target = plan.target(i);
                    for (var file : projection.files().get(i).entrySet()) {
                        completeFile(target.resolve(file.getKey()), file.getValue(), true);
                        AdmissionIo.at("BOOTSTRAP_TARGET_" + i + "_" + file.getKey() + "_FORCED");
                    }
                    verifyPayloads(target, plan.payloads().get(i)); AdmissionIo.at("BOOTSTRAP_TARGET_" + i + "_VERIFIED");
                    completeFile(target.resolve("bootstrap-prepared.gsr"), plan.preparation(i), true);
                    AdmissionIo.at("BOOTSTRAP_PREPARATION_" + i + "_FORCED");
                }
                append(operation, plan.row(2, 2, tail.digest())); tail = AdmissionJournal.read(operation.resolve("operation.gsr"), plan).getLast();
                AdmissionIo.at("BOOTSTRAP_PREPARED_FORCED");
            }
            for (int i = 0; i < 3; i++) {
                verifyPayloads(plan.target(i), plan.payloads().get(i));
                AdmissionPaths.exact(plan.target(i).resolve("bootstrap-prepared.gsr"), plan.preparation(i));
            }
            if (tail.phase() == 2) {
                var fresh = project(builder, request, false);
                require(Arrays.equals(plan.encode(), fresh.plan().encode()), CONFLICTING_HISTORY, "source changed before commit decision");
                append(operation, plan.row(3, 3, tail.digest())); tail = AdmissionJournal.read(operation.resolve("operation.gsr"), plan).getLast();
                AdmissionIo.at("BOOTSTRAP_COMMITTING_FORCED");
            }
            if (tail.phase() == 3) {
                // Complete, owned preparations prove the only permitted receipt, even after a crash before pending creation.
                Path pending = operation.resolve("receipt.pending.gsr"), receipt = operation.resolve("receipt.gsr");
                if (!Files.exists(receipt, LinkOption.NOFOLLOW_LINKS)) {
                    completeFile(pending, plan.receipt(), true); AdmissionIo.at("BOOTSTRAP_RECEIPT_PENDING_FORCED");
                    AdmissionPaths.absent(receipt); Files.move(pending, receipt, StandardCopyOption.ATOMIC_MOVE);
                    AdmissionIo.at("BOOTSTRAP_RECEIPT_RENAMED");
                }
                AdmissionPaths.exact(receipt, plan.receipt());
                try (var channel = FileChannel.open(receipt, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) { channel.force(true); }
                AdmissionPaths.forceDirectory(operation); AdmissionIo.at("BOOTSTRAP_RECEIPT_PARENT_FORCED");
                append(operation, plan.row(4, 4, tail.digest())); AdmissionIo.at("BOOTSTRAP_COMMITTED_FORCED");
            }
            AdmissionPaths.exact(operation.resolve("receipt.gsr"), plan.receipt());
            for (int i = 0; i < 3; i++) {
                var target = plan.target(i);
                AdmissionPaths.publish(target.resolve("bootstrap-seal.pending.gsr"), target.resolve("bootstrap-seal.gsr"), plan.seal(i), "BOOTSTRAP_SEAL_" + i);
                AdmissionIo.at("BOOTSTRAP_SEAL_" + i + "_FORCED");
                AdmissionPaths.exact(target.resolve("bootstrap-seal.gsr"), plan.seal(i));
            }
            return plan.result();
        } finally {
            IOException failure = null;
            for (int i = owners.size() - 1; i >= 0; i--) try { owners.get(i).close(); }
            catch (IOException error) { if (failure == null) failure = error; else failure.addSuppressed(error); }
            if (failure != null) throw failure;
        }
    }

    static void verifyPartial(Path target, Map<String, byte[]> expected, AdmissionPlan plan, int index, int phase) throws IOException {
        for (var member : AdmissionPaths.inventory(target, plan.maximum())) {
            require(member.kind() == 1, INTEGRITY_FAILURE, "unexpected directory in bootstrap output");
            byte[] bytes = expected.get(member.name());
            if (member.name().equals("bootstrap-prepared.gsr")) bytes = plan.preparation(index);
            if (member.name().equals("bootstrap-seal.gsr") || member.name().equals("bootstrap-seal.pending.gsr")) {
                require(phase == 4, INTEGRITY_FAILURE, "local seal precedes global decision"); bytes = plan.seal(index);
            }
            require(bytes != null, INTEGRITY_FAILURE, "unknown member in bootstrap output");
            byte[] actual = AdmissionPaths.read(target.resolve(member.name()), bytes.length);
            require(actual.length == bytes.length || phase == 1 || phase == 4 && member.name().equals("bootstrap-seal.pending.gsr"),
                    INTEGRITY_FAILURE, "prepared payload became incomplete");
            require(Arrays.equals(actual, Arrays.copyOf(bytes, actual.length)), CONFLICTING_HISTORY, "bootstrap output differs from planned prefix");
        }
    }

    static void verifyPayloads(Path target, List<Member> expected) throws IOException {
        var actual = AdmissionPaths.inventory(target, 1L << 40).stream()
                .filter(member -> expected.stream().anyMatch(wanted -> wanted.name().equals(member.name()))).toList();
        require(actual.equals(expected), INTEGRITY_FAILURE, "forced payload inventory differs from plan");
    }

    static void completeFile(Path path, byte[] expected, boolean allowPartial) throws IOException {
        if (!Files.exists(path, LinkOption.NOFOLLOW_LINKS)) AdmissionPaths.write(path, expected);
        else {
            byte[] actual = AdmissionPaths.read(path, expected.length);
            require((allowPartial || actual.length == expected.length) && Arrays.equals(actual, Arrays.copyOf(expected, actual.length)),
                    CONFLICTING_HISTORY, "existing member differs from exact operation");
            try (var channel = FileChannel.open(path, StandardOpenOption.WRITE, LinkOption.NOFOLLOW_LINKS)) {
                channel.position(actual.length); AdmissionPaths.write(channel, Arrays.copyOfRange(expected, actual.length, expected.length)); channel.force(true);
            }
            AdmissionPaths.forceDirectory(path.getParent());
        }
    }

    static void append(Path operation, byte[] row) throws IOException {
        Path journal = operation.resolve("operation.gsr");
        try (var channel = FileChannel.open(journal, StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND, LinkOption.NOFOLLOW_LINKS)) {
            AdmissionPaths.write(channel, row); channel.force(true);
        }
        AdmissionPaths.forceDirectory(operation);
    }

    static void operationInventory(Path operation) throws IOException {
        for (var member : AdmissionPaths.inventory(operation, 8L * META)) require(member.kind() == 1 && OPERATION_FILES.contains(member.name()),
                INTEGRITY_FAILURE, "unknown coordinator member");
    }

    static ReplicationBootstrapResult readResult(Path requested) {
        return guarded(() -> {
            Path operation = AdmissionPaths.safe(requested);
            try (var owner = AdmissionPaths.own(operation.resolve("operation.lock"), false)) {
                operationInventory(operation);
                var plan = AdmissionPlan.receipt(AdmissionPaths.read(operation.resolve("receipt.gsr"), META));
                require(plan.operation().equals(operation), CONFLICTING_HISTORY, "coordinator path differs from retained plan");
                AdmissionPaths.recheck(object(plan.descriptor().get("operation")));
                AdmissionPaths.exact(operation.resolve("plan.gsr"), plan.encode());
                require(AdmissionJournal.read(operation.resolve("operation.gsr"), plan).getLast().phase() == 4,
                        INTEGRITY_FAILURE, "global decision has not been durably completed");
                require(!Files.exists(operation.resolve("cleanup.gsr"), LinkOption.NOFOLLOW_LINKS), INTEGRITY_FAILURE, "committed bootstrap has cleanup authority");
                return plan.result();
            }
        });
    }

    interface Action<R> { R run() throws IOException; }
    static <R> R guarded(Action<R> action) {
        try { return action.run(); }
        catch (DurableOperationException failure) {
            var reason = switch (failure.reason()) {
                case IDENTITY_MISMATCH, UNSUPPORTED_FORMAT -> PROTOCOL_MISMATCH;
                case CAPACITY_EXCEEDED -> CAPACITY_EXCEEDED;
                case IO_FAILURE, STORAGE_IN_USE, TARGET_EXISTS, TARGET_INVALID, OPERATION_IN_PROGRESS, UNSUPPORTED_FILESYSTEM -> STORAGE_FAILURE;
                case CLOSED -> CLOSED;
                default -> INTEGRITY_FAILURE;
            };
            throw failure(reason, "core backup transfer rejected", failure);
        } catch (DurabilityException failure) {
            var reason = switch (failure.reason()) {
                case INCOMPATIBLE_STORAGE -> PROTOCOL_MISMATCH;
                case CAPACITY_EXCEEDED, SEQUENCE_EXHAUSTED -> CAPACITY_EXCEEDED;
                case STORAGE_IN_USE, STORAGE_ACCESS, UNSUPPORTED_FILESYSTEM, IO_FAILURE -> STORAGE_FAILURE;
                case CLOSED -> CLOSED;
                default -> INTEGRITY_FAILURE;
            };
            throw failure(reason, "core canonical transfer rejected", failure);
        } catch (java.io.EOFException | java.nio.charset.CharacterCodingException failure) {
            throw failure(INTEGRITY_FAILURE, "incomplete or noncanonical authority record", failure);
        } catch (IOException failure) { throw failure(STORAGE_FAILURE, "offline authority IO failed; retained outputs require exact resume or cleanup", failure); }
        catch (ArithmeticException failure) { throw failure(CAPACITY_EXCEEDED, "offline byte arithmetic overflow", failure); }
    }
}
