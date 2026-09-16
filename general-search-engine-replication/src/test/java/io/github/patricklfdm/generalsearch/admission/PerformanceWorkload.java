package io.github.patricklfdm.generalsearch.admission;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;

/** Published-V4-compatible workload, compiled independently for the two implementations. */
public final class PerformanceWorkload {
    public static final List<String> OPERATIONS = List.of("ADD", "UPDATE", "REMOVE", "ADD_ALL", "UPDATE_ALL",
            "REMOVE_ALL", "INDEX_DROP", "INDEX_CREATE", "GET", "QUERY");
    public record Plan(Map<String, Object> document, Map<String, Object> smoke, String digest) {
        public int number(String name) { return Math.toIntExact(((Number) smoke.get(name)).longValue()); }
    }
    private PerformanceWorkload() { }
    public static SearchEngineBuilder<Integer, Doc> builder() {
        return AdmissionSemanticModel.builder().config(new SnapshotEngineConfig(31, 16, java.time.Duration.ofNanos(1_234_567)));
    }
    @SuppressWarnings("unchecked")
    public static Plan plan(Path path) throws Exception {
        byte[] bytes = Files.readAllBytes(path);
        AdmissionJson.require(bytes.length <= 65536, "plan bound");
        var document = (Map<String, Object>) AdmissionJson.parse(new String(bytes, StandardCharsets.UTF_8));
        AdmissionJson.require(document.get("schema").equals("gse-v50-phase6-plan-v1"), "plan version");
        var smoke = (Map<String, Object>) document.get("localSmoke");
        return new Plan(document, smoke, hash(bytes));
    }
    public static String hash(byte[] bytes) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch (Exception error) { throw new IllegalStateException(error); }
    }
    public static String digest(Object value) { return hash(AdmissionJson.canonical(value).getBytes(StandardCharsets.US_ASCII)); }
    public static Doc document(int id, int revision, int seed) {
        return new Doc(id, "Java " + id, (id + revision + seed) % 3 == 0 ? "news" : "guide",
                (id * 17 + revision + seed) % 1000, "java search memory revision " + revision);
    }
    public static DurableStorageConfig<Integer, Doc> storage(Path path) {
        return DurableStorageConfig.builder(path, new Codec()).format(new DurableStorageFormat("gse-durable", 1, 2))
                .storageIdentity("performance-store").schemaIdentity("semantic-schema")
                .maxEncodedKeyBytes(1024).maxEncodedDocumentBytes(4096).maxBulkElements(16).maxDocuments(1024)
                .checkpointWalBytes(32L << 20).maxRetainedBytes(128L << 20).maxDerivedStateBytes(4L << 20).build();
    }
    public static void populate(DurableSearchEngine<Integer, Doc> engine, Plan plan) {
        var docs = new ArrayList<Doc>();
        for (int id = 1; id <= plan.number("corpusDocuments"); id++) {
            docs.add(document(id, 0, plan.number("seed")));
            if (docs.size() == plan.number("loadBulkElements")) { engine.addAll(docs).join(); docs.clear(); }
        }
        AdmissionJson.require(docs.isEmpty(), "corpus/load divisor");
    }
    public static Map<String, Object> semantic(DurableSearchEngine<Integer, Doc> engine) {
        return Map.of("sequence", engine.durabilityMetrics().currentSequence(), "report", AdmissionSemanticModel.report(engine));
    }
    public static Map<String, Object> execute(DurableSearchEngine<Integer, Doc> engine, Plan plan, String window, int firstCycle, int cycles) {
        var rows = new ArrayList<Object>();
        long begin = System.nanoTime();
        for (int cycle = firstCycle; cycle < firstCycle + cycles; cycle++) {
            for (String operation : OPERATIONS) {
                int id = 1 + cycle % plan.number("corpusDocuments"), temporary = 100000 + cycle * 100;
                var docs = new ArrayList<Doc>(); var keys = new ArrayList<Integer>();
                int count = operation.endsWith("_ALL") ? plan.number("mutationBulkElements") : 1;
                for (int i = 0; i < count; i++) {
                    int key = operation.startsWith("UPDATE") ? 1 + (cycle + i) % plan.number("corpusDocuments") : temporary + i;
                    keys.add(key); docs.add(document(key, cycle + 1, plan.number("seed")));
                }
                long before = engine.durabilityMetrics().currentSequence(), start = System.nanoTime();
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
                    case "GET" -> answer = engine.get(id).toString();
                    case "QUERY" -> answer = engine.search(Query.and(Query.eq(CATEGORY, "guide"), Query.term(TEXT, "java")))
                            .stream().map(Doc::id).toList();
                    default -> throw new IllegalArgumentException(operation);
                }
                long end = System.nanoTime(), after = engine.durabilityMetrics().currentSequence();
                var row = new TreeMap<String, Object>();
                row.put("cycle", cycle); row.put("operation", operation); row.put("outcome", "success");
                row.put("beforeSequence", before); row.put("afterSequence", after);
                row.put("startNanos", start); row.put("endNanos", end); row.put("elapsedNanos", end - start);
                row.put("documents", operation.startsWith("INDEX") || operation.equals("QUERY") ? 0 : count);
                row.put("answerDigest", digest(answer)); rows.add(row);
            }
        }
        long end = System.nanoTime();
        return Map.of("window", window, "startNanos", begin, "endNanos", end, "elapsedNanos", end - begin,
                "rows", rows, "resources", PerformanceTelemetry.resources());
    }
}
