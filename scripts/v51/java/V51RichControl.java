package io.github.patricklfdm.generalsearch.admission;

import static io.github.patricklfdm.generalsearch.admission.AdmissionSemanticModel.*;
import io.github.patricklfdm.generalsearch.durability.*;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Published V4.4 semantic oracle execution only, deliberately not a benchmark.
 * Full state scans after each operation are not part of the future timed adapter. */
public final class V51RichControl {
    private static void save(Path path, Object value) throws Exception {
        Files.writeString(path, AdmissionJson.canonical(value) + "\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
    }
    private static Map<String,Object> state(DurableSearchEngine<Integer,Doc> engine) {
        return Map.of("sequence", engine.durabilityMetrics().currentSequence(), "indexCount", engine.metrics().registeredIndexCount(),
                "documents", engine.search(doc -> true).stream().map(d -> List.of(d.id(), d.title(), d.category(), d.price(), d.body())).toList());
    }
    private static Map<String,Object> inventory(Path directory) throws Exception {
        var result = new TreeMap<String,Object>();
        try (var paths = Files.list(directory)) {
            for (Path path : paths.toList()) {
                if (!Files.isRegularFile(path) || Files.isSymbolicLink(path)) throw new IllegalStateException("backup member");
                result.put(path.getFileName().toString(), Map.of("size", Files.size(path), "sha256", V51RichWorkload.hash(Files.readAllBytes(path))));
            }
        }
        return result;
    }
    public static void main(String[] args) throws Exception {
        Path root = Path.of(args[0]); var plan = V51RichWorkload.plan(Path.of(args[1]));
        Path core = Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        save(root.resolve("identity.json"), Map.of("pid", ProcessHandle.current().pid(), "javaRuntime", System.getProperty("java.runtime.version"),
                "javaVendor", System.getProperty("java.vendor"), "javaMajor", Runtime.version().feature(),
                "jvmArguments", ManagementFactory.getRuntimeMXBean().getInputArguments(), "coreSource", core.toString(),
                "coreSha256", V51RichWorkload.hash(Files.readAllBytes(core)), "planFileSha256", plan.digest(),
                "execution", "published-v4.4-rich-semantics-only", "performanceMeasured", false));
        try (var engine = V51RichWorkload.builder().buildDurable(V51RichWorkload.storage(root.resolve("store")))) {
            V51RichWorkload.populate(engine, plan);
            save(root.resolve("initial.json"), state(engine));
            engine.backup(new DurableBackupRequest(root.resolve("source"), 16L << 20)).join();
            save(root.resolve("source-before.json"), inventory(root.resolve("source")));
            int cycle = 0, ordinal = 0;
            for (String window : List.of("warmup", "baseline-a", "instrumented-a", "instrumented-b", "baseline-b")) {
                int count = plan.number(window.equals("warmup") ? "warmupCycles" : "cyclesPerWindow");
                for (int repeat = 0; repeat < count; repeat++, cycle++) {
                    for (String operation : V51RichWorkload.OPERATIONS) {
                        var row = new LinkedHashMap<>(V51RichWorkload.operation(engine, plan, window, cycle, operation, ++ordinal));
                        row.put("state", state(engine));
                        Files.writeString(root.resolve("calls.jsonl"), AdmissionJson.canonical(row) + "\n", StandardCharsets.UTF_8,
                                StandardOpenOption.CREATE, StandardOpenOption.APPEND);
                    }
                }
            }
            engine.checkpoint().join();
            save(root.resolve("final.json"), state(engine));
            save(root.resolve("source-after.json"), inventory(root.resolve("source")));
        }
        try (var engine = V51RichWorkload.builder().buildDurable(V51RichWorkload.storage(root.resolve("store")))) {
            save(root.resolve("reopened.json"), state(engine));
        }
        var restored = V51RichWorkload.storage(root.resolve("restored"));
        V51RichWorkload.builder().restoreDurableBackup(root.resolve("source"), restored);
        try (var engine = V51RichWorkload.builder().buildDurable(restored)) {
            save(root.resolve("restored.json"), state(engine));
        }
        System.out.println("v51RichControl=PASS execution=published-v4.4-rich-semantics-only performanceMeasured=false");
    }
}
