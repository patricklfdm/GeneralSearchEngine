package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.io.IOException;
import java.nio.file.Path;
import java.util.*;

/** Complete offline projection. Summary values are never deletion or commit authority. */
record AutomaticBootstrapPlan(Record record, byte[] binding) {
    static final String BINDING = "bootstrap-binding.gsr";
    static final String HASH_ZERO = "0".repeat(64);
    static final List<String> STATES = List.of("PREPARING", "PREPARED", "COMMITTING", "COMMITTED");
    AutomaticBootstrapPlan {
        binding = binding.clone();
        var descriptor = descriptor(binding);
        need(descriptor.keySet().equals(Set.of("operation", "source", "application", "replicas", "sourceInventory")), "bootstrap descriptor fields");
        need(AdmissionConfiguration.path(descriptor.get("operation")).toString().equals(record.value().get("operationPath")), "operation binding");
        need(Objects.equals(descriptor.get("source")==null ? null : AdmissionConfiguration.path(descriptor.get("source")).toString(),record.value().get("sourcePath")),"source path binding");
        var genesis=decode(unbase(record.value().get("genesis")),"GENESIS").value();
        need(Objects.equals(genesis.get("sourceDigest"),descriptor.get("source")==null?null:sha(canonical(descriptor.get("sourceInventory")))),"source inventory digest");
        var manifest=decode(unbase(record.value().get("manifest")),"MANIFEST").value();
        var application=object(descriptor.get("application"));
        need(application.keySet().equals(Set.of("documentType","idField","fields","textFields","indexes","snapshot","planner")),"application descriptor fields");
        need(sha(canonical(list(application.get("indexes")).stream().map(String.class::cast).sorted().toList())).equals(manifest.get("indexesDigest")),"bound startup indexes");
        var targets = list(record.value().get("targets"));
        var locals = list(descriptor.get("replicas")); need(locals.size() == 3, "binding voter count");
        for (int i = 0; i < 3; i++) {
            var t = object(targets.get(i)); var local = object(locals.get(i));
            var core=object(local.get("materialization"));
            need(sha(canonical(Map.of("schemaIdentity",core.get("schemaIdentity"),"application",application))).equals(manifest.get("schemaDigest")),"bound application schema");
            need(core.get("codecId").equals(manifest.get("codecId")) && number(core,"codecVersion")==number(manifest,"codecVersion"),"bound codec identity");
            need(Arrays.equals(canonical(local.get("replicationBounds")),canonical(t.get("bounds"))),"bound replication limits");
            need(AdmissionConfiguration.path(local.get("target")).toString().equals(t.get("authorityPath"))
                    && AdmissionConfiguration.path(object(local.get("materialization")).get("directory")).toString().equals(t.get("materializationPath"))
                    && local.get("node").equals(t.get("node")), "bound target paths");
            var files = list(t.get("files"));
            var names = files.stream().map(x -> text(object(x), "path")).toList();
            var expected = new TreeSet<>(AutomaticAdmission.INITIAL); expected.add(BINDING);
            need(names.equals(List.copyOf(expected)), "public bootstrap inventory");
            var bound = object(files.stream().filter(x -> object(x).get("path").equals(BINDING)).findFirst().orElseThrow());
            need(number(bound, "size") == binding.length && bound.get("sha256").equals(sha(binding)), "descriptor inventory hash");
        }
    }
    @Override public byte[] binding() { return binding.clone(); }
    static Map<String,Object> descriptor(byte[] bytes) {
        return object(ReplicaJson.decode(unbase(decode(bytes, "BOOTSTRAP_BINDING").value().get("descriptor")), META));
    }
    Map<String,Object> descriptor() { return descriptor(binding); }
    Record manifest() { return decode(unbase(record.value().get("manifest")), "MANIFEST"); }
    byte[] genesis() { return unbase(record.value().get("genesis")); }
    Path operation() { return Path.of(text(record.value(), "operationPath")); }
    Path target(int i) { return Path.of(text(targetValue(i), "authorityPath")); }
    Map<String,Object> targetValue(int i) { return object(list(record.value().get("targets")).get(i)); }
    long maximum() { return number(record.value(), "maxOperationBytes"); }
    String digest() { return record.digest(); }
    List<Map<String,byte[]>> payloads() {
        return nodes(manifest().value()).stream().map(n -> payloads(manifest(), genesis(), binding, n)).toList();
    }
    static Map<String,byte[]> payloads(Record manifest, byte[] genesis, byte[] binding, String node) {
        var files = new TreeMap<String,byte[]>(); String m = manifest.digest();
        files.put("replica.lock", new byte[0]); files.put("manifest.gsr", manifest.bytes()); files.put("genesis.gsr", genesis);
        files.put(BINDING, binding);
        files.put("node.gsr", encode("NODE", Map.of("manifestDigest", m, "node", node, "origin", "BOOTSTRAP")));
        files.put("storage-ready.gsr", encode("READY", Map.of("manifestDigest", m, "node", node, "genesisDigest", AutomaticRecords.digest(genesis))));
        for (var journal : Map.of("promises.gsr", 4, "accepted.gsr", 24, "proofs.gsr", 6).entrySet()) {
            byte[] header = encode("JOURNAL", Map.of("manifestDigest", m, "node", node, "recordKind", journal.getValue()));
            if (journal.getValue() == 4) {
                var promise = new LinkedHashMap<String,Object>(); promise.put("manifestDigest", m); promise.put("epoch", 1L);
                promise.put("proposer", null); promise.put("incarnation", ZERO);
                byte[] p = encode("PROMISE", promise), both = Arrays.copyOf(header, header.length + p.length);
                System.arraycopy(p, 0, both, header.length, p.length); header = both;
            }
            files.put(journal.getKey(), header);
        }
        return files;
    }
    static List<Map<String,Object>> inventory(Map<String,byte[]> files) {
        return files.entrySet().stream().sorted(Map.Entry.comparingByKey()).map(e -> Map.<String,Object>of(
                "path", e.getKey(), "size", (long)e.getValue().length, "sha256", sha(e.getValue()))).toList();
    }
    byte[] preparation(int i) {
        return encode("PREPARED", Map.of("node", targetValue(i).get("node"), "planDigest", digest(),
                "manifestDigest", manifest().digest(), "inventoryDigest", sha(canonical(targetValue(i).get("files")))));
    }
    byte[] receipt() {
        return encode("RECEIPT", Map.of("plan", b64(record.bytes()), "preparations",
                java.util.stream.IntStream.range(0,3).mapToObj(i -> b64(preparation(i))).toList()));
    }
    byte[] seal(int i) { return encode("SEAL", Map.of("node", targetValue(i).get("node"), "receipt", b64(receipt()))); }
    byte[] row(int phase) {
        return encode("DECISION", Map.of("planDigest", digest(), "sequence", (long)phase, "state", STATES.get(phase-1),
                "previousDigest", phase == 1 ? HASH_ZERO : AutomaticRecords.digest(row(phase-1))));
    }
    ReplicationBootstrapPlan summary() {
        var m = manifest().value(); var g = decode(genesis(), "GENESIS").value();
        return new ReplicationBootstrapPlan(new ReplicationGroupId(UUID.fromString(text(m,"groupId"))), text(m,"configurationId"),
                ReplicationBootstrapSource.valueOf(text(g,"source")), record.value().get("sourcePath") == null ? null : Path.of(text(record.value(),"sourcePath")),
                java.util.stream.IntStream.range(0,3).mapToObj(this::target).toList(), digest());
    }
    ReplicationBootstrapResult result() {
        var m = manifest(); return new ReplicationBootstrapResult(operation(), summary(), m.digest(), AutomaticRecords.digest(genesis()),
                UUID.fromString(text(m.value(),"historyId")), number(m.value(),"baseSequence"), AutomaticRecords.digest(receipt()));
    }
    void checkBudget() {
        long total = record.bytes().length + binding.length + 2L * receipt().length;
        for (int p=1;p<=4;p++) total = Math.addExact(total,row(p).length);
        for (int i=0;i<3;i++) {
            long bytes = payloads().get(i).values().stream().mapToLong(b -> b.length).sum() + preparation(i).length + 2L * seal(i).length;
            var b = object(targetValue(i).get("bounds"));
            capacity(bytes <= number(b,"maxRetainedLogBytes") && seal(i).length <= number(b,"maxSnapshotStagingBytes"), "bootstrap local byte bound");
            total = Math.addExact(total,bytes);
        }
        capacity(total <= maximum(), "bootstrap aggregate byte bound");
    }
    void recheckPaths() throws IOException {
        AdmissionPaths.recheck(object(descriptor().get("operation")));
        if (descriptor().get("source") != null) AdmissionPaths.recheck(object(descriptor().get("source")));
        for (Object item : list(descriptor().get("replicas"))) {
            var local = object(item); AdmissionPaths.recheck(object(local.get("target")));
            AdmissionPaths.recheck(object(object(local.get("materialization")).get("directory")));
        }
    }
}
