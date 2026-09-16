package io.github.patricklfdm.generalsearch.admission;

import java.nio.file.Path;
import java.util.*;
import io.github.patricklfdm.generalsearch.durability.DurableBackupRequest;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;

/** Compiled and run with the checksum-pinned published V4.4 core only. */
public final class V50PerformanceControl {
    private V50PerformanceControl() { }
    public static void main(String[] args) throws Exception {
        String command = args[0]; Path root = Path.of(args[1]); var plan = PerformanceWorkload.plan(Path.of(args[2]));
        String source = Path.of(SearchEngine.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
        var result = new TreeMap<String, Object>(); result.put("identity", PerformanceTelemetry.identity(source, plan.digest()));
        var builder = PerformanceWorkload.builder(); var storage = PerformanceWorkload.storage(root.resolve("control-" + command));
        if (command.equals("restore")) builder.restoreDurableBackup(root.resolve("export"), storage);
        try (var engine = builder.buildDurable(storage)) {
            var windows = new ArrayList<Object>();
            if (command.equals("measure")) {
                PerformanceWorkload.populate(engine, plan);
                engine.backup(new DurableBackupRequest(root.resolve("source"), 16L << 20)).join();
                windows.add(PerformanceWorkload.execute(engine, plan, "warmup", 0, plan.number("warmupCycles")));
                int cycle = plan.number("warmupCycles");
                for (String name : List.of("baseline-a", "instrumented-a", "instrumented-b", "baseline-b")) {
                    windows.add(PerformanceWorkload.execute(engine, plan, name, cycle, plan.number("cyclesPerWindow")));
                    cycle += plan.number("cyclesPerWindow");
                }
            }
            result.put("windows", windows); result.put("semantic", PerformanceWorkload.semantic(engine));
        }
        System.out.println(AdmissionJson.canonical(result));
    }
}
