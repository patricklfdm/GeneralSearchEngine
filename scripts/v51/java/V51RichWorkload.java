package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.*;

/** Common-core public workload. Compiled separately against each admitted core JAR.
 * The operation method issues exactly one API call; no strong sequence probes.
 * Its payload encoder describes the request and is not a durable-vote observer. */
public final class V51RichWorkload {
    public static final List<String> OPERATIONS = List.of("ADD", "UPDATE", "REMOVE", "ADD_ALL", "UPDATE_ALL",
            "REMOVE_ALL", "INDEX_DROP", "INDEX_CREATE", "GET", "QUERY");
    public record Plan(Map<String,Object> document, Map<String,Object> smoke, String digest) {
        public int number(String name) { return Math.toIntExact(((Number)smoke.get(name)).longValue()); }
    }
    private V51RichWorkload() { }
    @SuppressWarnings("unchecked")
    public static Plan plan(Path path) throws Exception {
        byte[] bytes = Files.readAllBytes(path);
        AdmissionJson.require(bytes.length <= 65536, "plan size");
        var value = (Map<String,Object>)AdmissionJson.parse(new String(bytes, StandardCharsets.UTF_8));
        AdmissionJson.require(value.get("schema").equals("gse-v51-phase6-plan-v1")
                && value.get("preset").equals("v5.1-phase6-local-smoke-v1"), "local plan identity");
        return new Plan(value, (Map<String,Object>)value.get("localSmoke"), hash(bytes));
    }
    public static SearchEngineBuilder<Integer,Doc> builder() {
        return AdmissionSemanticModel.builder().config(new SnapshotEngineConfig(31, 16, Duration.ofNanos(1234567)));
    }
    public static DurableStorageConfig<Integer,Doc> storage(Path path) {
        return DurableStorageConfig.builder(path, new Codec()).format(new DurableStorageFormat("gse-durable", 1, 2))
                .storageIdentity("performance-store").schemaIdentity("semantic-schema")
                .maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(4096).maxBulkElements(16).maxDocuments(1024)
                .checkpointWalBytes(32L << 20).maxRetainedBytes(128L << 20).maxDerivedStateBytes(4L << 20).build();
    }
    public static String hash(byte[] value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value)); }
        catch (Exception error) { throw new IllegalStateException(error); }
    }
    public static String digest(Object value) { return hash(AdmissionJson.canonical(value).getBytes(StandardCharsets.US_ASCII)); }
    public static Doc document(int key, int revision, int seed) {
        return new Doc(key, "Java " + key, (key + revision + seed) % 3 == 0 ? "news" : "guide",
                (key * 17 + revision + seed) % 1000, "java search memory revision " + revision);
    }
    public static void populate(DurableSearchEngine<Integer,Doc> engine, Plan plan) {
        var batch = new ArrayList<Doc>();
        for (int id = 1; id <= plan.number("corpusDocuments"); id++) {
            batch.add(document(id, 0, plan.number("seed")));
            if (batch.size() == plan.number("loadBulkElements")) { engine.addAll(batch).join(); batch.clear(); }
        }
        AdmissionJson.require(batch.isEmpty(), "load divisor");
    }
    private static void blob(DataOutputStream out, byte[] raw) throws IOException { out.writeInt(raw.length); out.write(raw); }
    private static byte[] payload(String operation, List<Integer> keys, List<Doc> docs) throws IOException {
        if (operation.equals("GET") || operation.equals("QUERY")) return new byte[0];
        var bytes = new ByteArrayOutputStream(); var out = new DataOutputStream(bytes); out.writeShort(1);
        if (operation.startsWith("INDEX")) {
            String value = operation.equals("INDEX_DROP") ? "category" :
                    AdmissionJson.canonical(Map.of("field", "category", "kind", "equality", "analyzer", ""));
            blob(out, value.getBytes(StandardCharsets.UTF_8));
        } else {
            out.writeInt(keys.size()); var codec = new Codec();
            for (int i = 0; i < keys.size(); i++) {
                blob(out, codec.encodeKey(keys.get(i)));
                if (!operation.startsWith("REMOVE")) blob(out, codec.encodeDocument(docs.get(i)));
            }
        }
        out.flush(); return bytes.toByteArray();
    }
    public static Map<String,Object> operation(DurableSearchEngine<Integer,Doc> engine, Plan plan,
            String window, int cycle, String operation, int ordinal) throws IOException {
        AdmissionJson.require(OPERATIONS.contains(operation), "workload operation");
        int count = operation.endsWith("_ALL") ? plan.number("mutationBulkElements") : 1;
        var keys = new ArrayList<Integer>(); var docs = new ArrayList<Doc>();
        if (operation.equals("GET")) keys.add(1 + cycle % plan.number("corpusDocuments"));
        else if (!operation.startsWith("INDEX") && !operation.equals("QUERY")) {
            for (int i = 0; i < count; i++) {
                int key = operation.startsWith("UPDATE") ? 1 + (cycle + i) % plan.number("corpusDocuments") : 100000 + cycle * 100 + i;
                keys.add(key);
                if (operation.startsWith("ADD") || operation.startsWith("UPDATE")) docs.add(document(key, cycle + 1, plan.number("seed")));
            }
        }
        var row = new LinkedHashMap<String,Object>();
        row.put("ordinal", ordinal); row.put("window", window); row.put("cycle", cycle); row.put("operation", operation);
        row.put("keys", keys); row.put("payloadSha256", hash(payload(operation, keys, docs)));
        // These diagnostics do not issue currentSequence(), which is a strong read in automatic mode.
        row.put("beforeSequence", engine.durabilityMetrics().currentSequence());
        Object answer = null;
        switch (operation) {
            case "ADD" -> engine.add(docs.getFirst()).join();
            case "UPDATE" -> engine.update(docs.getFirst()).join();
            case "REMOVE" -> engine.remove(keys.getFirst()).join();
            case "ADD_ALL" -> engine.addAll(docs).join();
            case "UPDATE_ALL" -> engine.updateAll(docs).join();
            case "REMOVE_ALL" -> engine.removeAll(keys).join();
            case "INDEX_DROP" -> engine.dropIndex("category").join();
            case "INDEX_CREATE" -> engine.createIndex(IndexDefinition.equality(CATEGORY)).join();
            case "GET" -> answer = engine.get(keys.getFirst()).toString();
            case "QUERY" -> answer = engine.search(Query.and(Query.eq(CATEGORY, "guide"), Query.term(TEXT, "java")))
                    .stream().map(Doc::id).toList();
            default -> throw new IllegalArgumentException(operation);
        }
        row.put("afterSequence", engine.durabilityMetrics().currentSequence());
        row.put("answer", answer); row.put("answerSha256", digest(answer)); row.put("outcome", "SUCCESS");
        return row;
    }
}
