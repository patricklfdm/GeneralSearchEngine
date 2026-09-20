package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Test-only sealed directory construction; never an automatic bootstrap acceptance claim. */
final class V51StorageFixture {
    static Map<String, Object> samples() throws Exception {
        try (var in = V51StorageFixture.class.getResourceAsStream("/replication/v51/format-fixtures.json")) {
            return object(object(io.github.patricklfdm.generalsearch.admission.AdmissionJson.parse(new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8))).get("storage"));
        }
    }
    static Map<String, Object> copy(Map<String, Object> value) { return object(ReplicaJson.decode(canonical(value), IMAGE)); }
    static byte[] setup(Path root) throws Exception {
        var samples = samples(); byte[] manifest = unbase(samples.get("MANIFEST")), genesis = unbase(samples.get("GENESIS"));
        var plan = copy(decode(unbase(samples.get("PLAN")), "PLAN").value());
        plan.put("operationPath", root.resolve("operation").toString());
        var inventories = new ArrayList<Map<String, byte[]>>();
        for (int i = 1; i <= 3; i++) {
            String node = "node-" + i; var files = new java.util.TreeMap<String, byte[]>();
            files.put("replica.lock", new byte[0]); files.put("manifest.gsr", manifest); files.put("genesis.gsr", genesis);
            files.put("node.gsr", encode("NODE", Map.of("manifestDigest", digest(manifest), "node", node, "origin", "BOOTSTRAP")));
            files.put("storage-ready.gsr", encode("READY", Map.of("manifestDigest", digest(manifest), "node", node, "genesisDigest", digest(genesis))));
            for (var row : Map.of("promises.gsr", 4, "accepted.gsr", 24, "proofs.gsr", 6).entrySet()) {
                byte[] bytes = encode("JOURNAL", Map.of("manifestDigest", digest(manifest), "node", node, "recordKind", row.getValue()));
                if (row.getValue() == 4) {
                    var value = new LinkedHashMap<String, Object>(); value.put("manifestDigest", digest(manifest));
                    value.put("epoch", 1L); value.put("proposer", null); value.put("incarnation", ZERO);
                    var out = new java.io.ByteArrayOutputStream(); out.write(bytes); out.write(encode("PROMISE", value)); bytes = out.toByteArray();
                }
                files.put(row.getKey(), bytes);
            }
            var target = object(list(plan.get("targets")).get(i - 1));
            target.put("authorityPath", root.resolve(node).toString()); target.put("materializationPath", root.resolve("app-" + i).toString());
            target.put("files", files.entrySet().stream().map(e -> Map.of("path", e.getKey(), "size", (long) e.getValue().length, "sha256", sha(e.getValue()))).toList());
            inventories.add(files);
        }
        byte[] planBytes = encode("PLAN", plan); var preps = new ArrayList<String>();
        for (int i = 1; i <= 3; i++) preps.add(b64(encode("PREPARED", Map.of("node", "node-" + i, "planDigest", digest(planBytes),
                "manifestDigest", digest(manifest), "inventoryDigest", sha(canonical(object(list(plan.get("targets")).get(i - 1)).get("files")))))));
        byte[] receipt = encode("RECEIPT", Map.of("plan", b64(planBytes), "preparations", preps));
        for (int i = 1; i <= 3; i++) {
            String node = "node-" + i; Path target = root.resolve(node); Files.createDirectory(target);
            var files = inventories.get(i - 1); files.put("bootstrap-prepared.gsr", unbase(preps.get(i - 1)));
            files.put("bootstrap-seal.gsr", encode("SEAL", Map.of("node", node, "receipt", b64(receipt))));
            for (var file : files.entrySet()) Files.write(target.resolve(file.getKey()), file.getValue());
        }
        return manifest;
    }
    static byte[] promise(byte[] manifest, long epoch) {
        return encode("PROMISE", Map.of("manifestDigest", digest(manifest), "epoch", epoch, "proposer", "node-" + ((epoch - 2) % 3 + 1),
                "incarnation", "11111111-1111-1111-1111-111111111111"));
    }
    static byte[] entry(byte[] manifest, long index, byte[] previous, int operation, byte[] payload) {
        return encode("ENTRY", Map.of("manifestDigest", digest(manifest), "originEpoch", 2L,
                "originIncarnation", "11111111-1111-1111-1111-111111111111", "index", index, "operation", operation,
                "previousEpoch", previous == null ? 1L : 2L, "previousIndex", index - 1, "previousDigest", previous == null ? digest(manifest) : digest(previous),
                "payload", b64(payload), "payloadDigest", sha(payload)));
    }
    static byte[] accept(byte[] manifest, byte[] entry, long epoch) {
        var value = copy(decode(promise(manifest, epoch), "PROMISE").value()); value.put("entry", b64(entry)); value.put("entryDigest", digest(entry));
        return encode("ACCEPT", value);
    }
    static byte[] proof(byte[] manifest, byte[] entry, long epoch) {
        var value = copy(decode(promise(manifest, epoch), "PROMISE").value()); var e = decode(entry, "ENTRY").value();
        value.put("index", number(e, "index")); value.put("entryDigest", digest(entry)); value.put("previousDigest", e.get("previousDigest"));
        value.put("receipts", List.of("node-1", "node-2").stream().map(n -> Map.of("voter", n,
                "digest", receipt("ACCEPT_ACK", digest(manifest), n, value, number(e, "index"), digest(entry)))).toList());
        return encode("PROOF", value);
    }
}
