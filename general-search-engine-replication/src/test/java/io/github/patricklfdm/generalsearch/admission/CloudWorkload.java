package io.github.patricklfdm.generalsearch.admission;

import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Supplier;
import java.util.function.LongSupplier;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;

/** Public V4-compatible cloud workload; independently compiled with the published control. */
public final class CloudWorkload {
    public record Plan(Map<String, Object> value, String digest) {
        public Map<String, Object> section(String key) { return map(value.get(key)); }
    }
    private CloudWorkload() { }
    @SuppressWarnings("unchecked") public static Map<String, Object> map(Object value) { return (Map<String, Object>) value; }
    public static int number(Map<String, Object> value, String key) { return Math.toIntExact(((Number) value.get(key)).longValue()); }
    public static Plan plan(Path path) throws Exception {
        byte[] bytes = Files.readAllBytes(path);
        AdmissionJson.require(bytes.length < 65536, "cloud plan bound");
        var value = map(AdmissionJson.parse(new String(bytes, StandardCharsets.UTF_8)));
        AdmissionJson.require(value.get("schema").equals("gse-v50-cloud-workload-plan-v1"), "cloud plan version");
        return new Plan(value, PerformanceWorkload.hash(bytes));
    }
    /** Shared control parameters; cloud resource admission is owned by the later runner integration. */
    public static Map<String,Object> parameters(Plan plan, String profile) {
        if (profile.equals("local-qualification")) return plan.section("localQualification");
        AdmissionJson.require(List.of("experiment","failure-drill","canonical").contains(profile), "unknown workload profile");
        var w=plan.section("workload");
        return Map.of("warmupCycles",number(w,"warmupSeconds"),"cyclesPerWindow",profile.equals("canonical")?120:30,
                "sustainedCalls",profile.equals("canonical")?6000:0,
                "healthyIntervalNanos",number(w,"healthyIntervalNanos"),"sustainedIntervalNanos",number(w,"sustainedIntervalNanos"));
    }
    public static DurableStorageConfig<Integer, Doc> storage(Path path, Plan plan) {
        var b = plan.section("application");
        return DurableStorageConfig.builder(path, new Codec()).format(new DurableStorageFormat("gse-durable", 1, 2))
                .storageIdentity((String)b.get("storageIdentity")).schemaIdentity((String)b.get("schema"))
                .maxEncodedKeyBytes(number(b,"maxEncodedKeyBytes")).maxEncodedDocumentBytes(number(b,"maxEncodedDocumentBytes"))
                .maxBulkElements(number(b,"maxBulkElements")).maxDocuments(number(b,"maxDocuments"))
                .checkpointWalBytes(number(b,"checkpointWalBytes")).maxRetainedBytes(number(b,"maxRetainedBytes"))
                .maxDerivedStateBytes(number(b,"maxDerivedStateBytes")).build();
    }
    public static void populate(DurableSearchEngine<Integer, Doc> engine, Plan plan) {
        int size = number(plan.section("workload"), "loadBulkElements");
        for (int first=1; first<=number(plan.value(),"corpusDocuments"); first+=size) {
            var docs = new ArrayList<Doc>();
            for (int i=0; i<size; i++) docs.add(PerformanceWorkload.document(first+i,0,17));
            engine.addAll(docs).join();
        }
    }
    public static Map<String, Object> state(DurableSearchEngine<Integer, Doc> engine, String label) {
        long before = engine.currentSequence(); var docs = engine.search(d -> true);
        long after = engine.currentSequence(); AdmissionJson.require(before == after, "ambiguous state cut");
        var codec = new Codec(); var encoded = docs.stream().map(d -> new String(codec.encodeDocument(d), StandardCharsets.UTF_8)).toList();
        for (int offset=0; offset<encoded.size(); offset+=256)
            CloudWorkloadTelemetry.record("states", Map.of("label",label,"sequence",after,"offset",offset,
                    "documents",encoded.subList(offset, Math.min(offset+256,encoded.size()))));
        var result = Map.<String,Object>of("label",label,"sequence",after,"count",docs.size(),
                "documentsSha256",PerformanceWorkload.digest(encoded),"indexCount",engine.metrics().registeredIndexCount());
        CloudWorkloadTelemetry.record("state-cuts",result); return result;
    }
    private static void until(long due) {
        long left;
        while ((left=due-System.nanoTime()) > 0) {
            try { TimeUnit.NANOSECONDS.sleep(left); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new IllegalStateException(e); }
        }
    }
    public static Map<String, Object> execute(DurableSearchEngine<Integer,Doc> engine, Plan plan, String profile, String name,
            int firstCycle, int calls, long interval, boolean sustained, Supplier<Map<String,Object>> status) throws Exception {
        AdmissionJson.require(calls > 0 && calls <= 60000 && interval >= 50000000L, "workload command bound");
        CloudWorkloadTelemetry.window = name; CloudWorkloadTelemetry.instrumented = name.startsWith("instrumented") || sustained;
        CloudWorkloadTelemetry.sample(status);
        parameters(plan, profile); // Reject unknown profile names before issuing any operation.
        boolean paced = profile.equals("local-qualification");
        String pacing = paced ? (String)plan.section("localQualification").get("pacing") : "fixed-rate";
        AdmissionJson.require(!paced || pacing.equals("completion-paced"), "local pacing contract");
        long maximum = paced ? TimeUnit.SECONDS.toNanos(number(plan.section("localQualification"),"maximumWindowSeconds"))
                : Math.addExact(Math.multiplyExact((long)calls, interval), TimeUnit.SECONDS.toNanos(1));
        int lanes = sustained ? 4 : 1;
        CloudWorkloadSchedule.Window measured;
        try (var executor = Executors.newFixedThreadPool(lanes)) {
            measured = CloudWorkloadSchedule.run(calls, lanes, interval, paced, maximum, new CloudWorkloadSchedule.Driver() {
                public long now() { return System.nanoTime(); }
                public void until(long due) { CloudWorkload.until(due); }
                public void await(CompletableFuture<Void> future, long deadline) throws Exception {
                    future.get(Math.max(0, deadline-System.nanoTime()), TimeUnit.NANOSECONDS);
                }
                public CompletableFuture<Void> submit(int call, long nominal, long due, long dispatched) {
                    return CompletableFuture.runAsync(() -> operation(engine, plan, name, firstCycle, call, nominal, due, dispatched, sustained, paced), executor);
                }
                public void missed(int call, long due, long observed, boolean pending) {
                    CloudWorkloadTelemetry.record("calls", Map.of("window",name,"call",call,"scheduledNanos",due,
                            "dispatchNanos",observed,"outcome","missed-slot","pendingLane",pending));
                }
            });
        }
        CloudWorkloadTelemetry.sample(status); CloudWorkloadTelemetry.check();
        var result = new TreeMap<String,Object>(Map.of("name",name,"firstCycle",firstCycle,"calls",calls,"intervalNanos",interval,
                "lanes",lanes,"startNanos",measured.start(),"endNanos",measured.end(),"missedSlots",0,"instrumented",CloudWorkloadTelemetry.instrumented));
        result.put("pacing",pacing);
        CloudWorkloadTelemetry.record("windows",result);
        return result;
    }
    private static void operation(DurableSearchEngine<Integer,Doc> engine, Plan plan, String window,
            int firstCycle, int call, long nominal, long due, long dispatched, boolean sustained, boolean local) {
        int cycle = firstCycle+call/10, lane=call%4, laneCall=call/4;
        String op = sustained ? (laneCall%4 == 3 ? "QUERY" : "UPDATE") : PerformanceWorkload.OPERATIONS.get(call%10);
        int size = op.endsWith("_ALL") ? 16 : 1;
        int revision = sustained ? laneCall+1 : cycle+1;
        var docs = new ArrayList<Doc>(); var keys = new ArrayList<Integer>();
        for (int i=0;i<size;i++) {
            int key = sustained ? lane+1 : op.startsWith("UPDATE") ? 1+(cycle+i)%4096 : 100000+cycle*100+i;
            keys.add(key); docs.add(PerformanceWorkload.document(key,revision,17));
        }
        long start=System.nanoTime(), before=engine.currentSequence(); Object answer=null;
        var row=new TreeMap<String,Object>(); row.put("call",call); row.put("cycle",cycle); row.put("lane",sustained?lane:0);
        row.put("operation",op); row.put("scheduledNanos",due); row.put("startNanos",start); row.put("beforeSequence",before);
        row.put("nominalScheduledNanos",nominal); row.put("dispatchNanos",dispatched);
        row.put("keys",op.startsWith("INDEX") || op.equals("QUERY") ? List.of() : op.equals("GET") ? List.of(1+cycle%4096) : keys);
        row.put("revision",revision); row.put("documents",op.startsWith("INDEX")||op.equals("QUERY") ? 0:size);
        try {
            switch(op) {
                case "ADD" -> engine.add(docs.getFirst()).join();
                case "UPDATE" -> engine.update(docs.getFirst()).join();
                case "REMOVE" -> engine.remove(keys.getFirst()).join();
                case "ADD_ALL" -> engine.addAll(docs).join();
                case "UPDATE_ALL" -> engine.updateAll(docs).join();
                case "REMOVE_ALL" -> engine.removeAll(keys).join();
                case "INDEX_DROP" -> engine.dropIndex("category").join();
                case "INDEX_CREATE" -> engine.createIndex(IndexDefinition.equality(CATEGORY)).join();
                case "GET" -> answer=engine.get(1+cycle%4096).toString();
                case "QUERY" -> {
                    Supplier<List<Integer>> query = () -> engine.search(Query.and(Query.eq(CATEGORY,"guide"),Query.term(TEXT,"java"))).stream().map(Doc::id).toList();
                    answer = local && sustained ? sampleLocalQuery(engine::currentSequence, query, row) : query.get();
                }
                default -> throw new IllegalArgumentException(op);
            }
            // The qualified attempt already captured both sequence samples. A later read
            // would reintroduce the race after the query has successfully finished.
            if (row.containsKey("readAttempts")) before=((Number)row.get("beforeSequence")).longValue();
            long after=row.containsKey("readAttempts") ? ((Number)row.get("afterSequence")).longValue() : engine.currentSequence();
            if (op.equals("QUERY")||op.equals("GET")) AdmissionJson.require(before==after,"ambiguous read cut");
            row.put("afterSequence",after); row.put("answerDigest",PerformanceWorkload.digest(answer)); row.put("outcome","success");
        } catch (RuntimeException error) { row.put("outcome","failed"); row.put("reason",error.toString()); throw error; }
        finally { row.put("endNanos",System.nanoTime()); CloudWorkloadTelemetry.record("calls",row); }
    }

    /** Local qualification only: retain bounded retries and charge all time to the call. */
    static <T> T sampleLocalQuery(LongSupplier sequence, Supplier<T> query, Map<String,Object> row) {
        var attempts = new ArrayList<Map<String,Object>>();
        row.put("readAttempts", attempts);
        for (int attempt=0; attempt<4; attempt++) {
            long start=System.nanoTime(), before=sequence.getAsLong();
            T answer=query.get();
            long after=sequence.getAsLong(), end=System.nanoTime();
            attempts.add(Map.of("beforeSequence",before,"afterSequence",after,"startNanos",start,
                    "endNanos",end,"answerDigest",PerformanceWorkload.digest(answer)));
            AdmissionJson.require(before<=after,"read sequence regression");
            if (before==after) {
                row.put("beforeSequence",before); row.put("afterSequence",after);
                return answer;
            }
        }
        throw new IllegalArgumentException("ambiguous read cut after 4 local attempts");
    }
}
