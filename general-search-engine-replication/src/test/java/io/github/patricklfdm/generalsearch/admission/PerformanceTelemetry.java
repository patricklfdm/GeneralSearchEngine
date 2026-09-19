package io.github.patricklfdm.generalsearch.admission;

import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Bounded in-memory observations. No filesystem writes occur inside measured hooks. */
public final class PerformanceTelemetry {
    private static boolean enabled;
    private static String window = "disabled";
    private static long windowStartedNanos;
    private static final List<Object> FORCES = new ArrayList<>(), EVENTS = new ArrayList<>();
    private static long wireAttempts, encodedAttemptBytes;
    private PerformanceTelemetry() { }
    public static synchronized boolean enabled() { return enabled; }
    public static synchronized void configure(String name, boolean value) {
        windowStartedNanos = System.nanoTime();
        window = name; enabled = value; FORCES.clear(); EVENTS.clear(); wireAttempts = 0; encodedAttemptBytes = 0;
    }
    public static synchronized void force(String kind, long start, long end) {
        // A follower may finish an old force after configure clears the lists.
        // Attribute only observations that began within the current window.
        if (!enabled || start < windowStartedNanos) return;
        AdmissionJson.require(FORCES.size() < 4096, "force observation bound");
        FORCES.add(Map.of("kind", kind, "startNanos", start, "endNanos", end, "elapsedNanos", end - start));
    }
    public static synchronized void event(String name, long index, long now) {
        if (!enabled || now < windowStartedNanos) return;
        AdmissionJson.require(EVENTS.size() < 4096, "event observation bound");
        EVENTS.add(Map.of("event", name, "index", index, "nanos", now));
    }
    public static synchronized void wire(int bytes) {
        if (!enabled) return;
        AdmissionJson.require(++wireAttempts <= 4096 && (encodedAttemptBytes += bytes) <= 8L << 20, "wire observation bound");
    }
    public static synchronized Map<String, Object> snapshot() {
        return Map.of("window", window, "enabled", enabled, "forces", List.copyOf(FORCES), "events", List.copyOf(EVENTS),
                "wireAttempts", wireAttempts, "encodedAttemptBytes", encodedAttemptBytes);
    }
    public static Map<String, Object> resources() {
        try {
            var memory = ManagementFactory.getMemoryMXBean().getHeapMemoryUsage();
            var result = new TreeMap<String, Object>();
            result.put("heapUsedBytes", memory.getUsed()); result.put("heapMaxBytes", memory.getMax());
            long gcCount = 0, gcMillis = 0;
            for (var gc : ManagementFactory.getGarbageCollectorMXBeans()) {
                gcCount += Math.max(0, gc.getCollectionCount()); gcMillis += Math.max(0, gc.getCollectionTime());
            }
            result.put("gcCount", gcCount); result.put("gcMillis", gcMillis);
            result.put("cpuNanos", ProcessHandle.current().info().totalCpuDuration().orElseThrow().toNanos());
            var status = Files.readAllLines(Path.of("/proc/self/status"));
            for (String key : List.of("VmRSS", "VmHWM")) {
                String line = status.stream().filter(s -> s.startsWith(key + ":")).findFirst().orElseThrow();
                result.put(key + "Bytes", Long.parseLong(line.split("\\s+")[1]) * 1024);
            }
            var io = new TreeMap<String, Object>();
            for (String line : Files.readAllLines(Path.of("/proc/self/io"))) {
                String[] parts = line.split(":\\s+"); io.put(parts[0], Long.parseLong(parts[1]));
            }
            result.put("processIo", io); return result;
        } catch (Exception error) { throw new IllegalStateException("Linux process metrics unavailable", error); }
    }
    public static Map<String, Object> identity(String coreSource, String planDigest) {
        return Map.of("pid", ProcessHandle.current().pid(), "javaRuntime", System.getProperty("java.runtime.version"),
                "javaVendor", System.getProperty("java.vendor"), "os", System.getProperty("os.name"),
                "architecture", System.getProperty("os.arch"), "jvmArguments", ManagementFactory.getRuntimeMXBean().getInputArguments(),
                "availableProcessors", Runtime.getRuntime().availableProcessors(), "coreSource", coreSource, "planSha256", planDigest);
    }
}
