package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import java.util.Map;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.admission.AdmissionJson;
import org.junit.jupiter.api.Test;

class V50OfflineFixtureAgreementTest {
    @org.junit.jupiter.api.io.TempDir Path root;

    @SuppressWarnings("unchecked")
    @Test
    void closedSourceInspectionChecksFrozenSnapshotSequenceAndProofAncestry() throws Exception {
        Map<String, Object> catalog;
        try (var input = getClass().getResourceAsStream("/replication/v50-admission-fixtures-v2.json")) {
            catalog = (Map<String, Object>) AdmissionJson.parse(new String(input.readAllBytes(), StandardCharsets.UTF_8));
        }
        int example = 0;
        for (var base : ((Map<String, Object>) catalog.get("bases")).values()) {
            var files = (Map<String, Object>) base;
            for (int cut = 0; cut < 4; cut++) {
                Path directory = Files.createDirectory(root.resolve("source-" + example++));
                for (var entry : files.entrySet()) if (entry.getKey().startsWith("node-1/")) {
                    Files.write(directory.resolve(entry.getKey().substring(7)), HexFormat.of().parseHex((String) entry.getValue()));
                }
                var manifest = AdmissionFormat.Manifest.read(bytes(files, "manifest.gsr"));
                byte[] snapshot = bytes(files, "snapshot-" + cut + ".gsr");
                var input = AdmissionFormat.decode(snapshot, 8, AdmissionFormat.IMAGE);
                ReplicaFormat.hash(input); input.readLong(); input.readLong(); int count = input.readInt(); long previousEpoch = 1;
                for (int i = 0; i < count; i++) {
                    long epoch = input.readLong(); UUID incarnation = ReplicaFormat.uuid(input); input.skipNBytes(65);
                    if (epoch > previousEpoch) Files.write(directory.resolve("promises.gsr"), AdmissionFormat.record(4, out -> {
                        ReplicaFormat.hash(out, manifest.digest()); ReplicaFormat.text(out, manifest.group().leader().value());
                        out.writeLong(epoch); ReplicaFormat.uuid(out, incarnation);
                    }), java.nio.file.StandardOpenOption.APPEND);
                    previousEpoch = epoch;
                }
                Path generation = Files.createDirectory(directory.resolve("generation-a"));
                Files.write(generation.resolve("snapshot.gsr"), snapshot);
                for (String journal : java.util.List.of("entries.gsr", "proofs.gsr")) Files.copy(directory.resolve(journal), generation.resolve(journal));
                UUID identity = UUID.fromString("44444444-4444-4444-4444-444444444444");
                byte[] seal = AdmissionFormat.record(11, out -> {
                    ReplicaFormat.hash(out, manifest.digest()); ReplicaFormat.text(out, "node-1"); ReplicaFormat.uuid(out, identity);
                    ReplicaFormat.hash(out, ReplicaFormat.frameDigest(snapshot));
                    for (String journal : java.util.List.of("entries.gsr", "proofs.gsr")) ReplicaFormat.hash(out, ReplicaFormat.frameDigest(Files.readAllBytes(generation.resolve(journal))));
                });
                Files.write(generation.resolve("generation.gsr"), seal);
                Files.write(directory.resolve("current.gsr"), AdmissionFormat.record(10, out -> {
                    ReplicaFormat.hash(out, manifest.digest()); ReplicaFormat.text(out, "node-1"); ReplicaFormat.text(out, "generation-a");
                    ReplicaFormat.uuid(out, identity); ReplicaFormat.hash(out, ReplicaFormat.frameDigest(seal)); out.writeByte(1);
                }));
                var before = AdmissionPaths.inventory(directory, 1 << 20);
                assertEquals(manifest.digest(), AdmissionNode.read(directory, 1 << 20).plan().manifest().digest());
                assertEquals(before, AdmissionPaths.inventory(directory, 1 << 20));
            }
        }
    }
    @SuppressWarnings("unchecked")
    @Test
    void productionReadersAgreeWithFrozenIndependentAuthorityBytes() throws Exception {
        Map<String, Object> catalog;
        try (var input = getClass().getResourceAsStream("/replication/v50-admission-fixtures-v2.json")) {
            catalog = (Map<String, Object>) AdmissionJson.parse(new String(input.readAllBytes(), StandardCharsets.UTF_8));
        }
        for (var base : ((Map<String, Object>) catalog.get("bases")).values()) {
            var files = (Map<String, Object>) base;
            var manifest = AdmissionFormat.Manifest.read(bytes(files, "manifest.gsr"));
            var genesis = AdmissionFormat.Genesis.read(bytes(files, "genesis.gsr"), manifest);
            var plan = AdmissionPlan.read(bytes(files, "plan.gsr"));
            assertEquals(genesis.base(), plan.manifest().base());
            assertArrayEquals(bytes(files, "receipt.gsr"), plan.receipt());
            assertArrayEquals(plan.encode(), AdmissionPlan.receipt(plan.receipt()).encode());
            for (int i = 0; i < 3; i++) {
                assertArrayEquals(bytes(files, "node-" + (i + 1) + "/bootstrap-prepared.gsr"), plan.preparation(i));
                assertArrayEquals(bytes(files, "node-" + (i + 1) + "/bootstrap-seal.gsr"), plan.seal(i));
            }
            byte[] damaged = bytes(files, "genesis.gsr"); damaged[damaged.length - 1] ^= 1;
            assertThrows(ReplicationException.class, () -> AdmissionFormat.Genesis.read(damaged, manifest));
        }
    }

    private static byte[] bytes(Map<String, Object> files, String name) {
        return HexFormat.of().parseHex((String) files.get(name));
    }
}
