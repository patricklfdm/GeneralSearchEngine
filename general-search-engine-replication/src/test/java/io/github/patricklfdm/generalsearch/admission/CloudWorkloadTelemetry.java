package io.github.patricklfdm.generalsearch.admission;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.*;

/** Test-only bounded streams. No measurement member is accumulated for the whole run. */
public final class CloudWorkloadTelemetry {
    public static volatile String window = "setup", fault = "none", cut = "";
    public static volatile boolean instrumented;
    public static Function<Object, Map<String, Object>> observer = ignored -> Map.of();
    private static Path root;
    private static final Map<String, Stream> streams = new HashMap<>();
    private static ScheduledExecutorService sampler;
    private static final AtomicReference<Throwable> failure = new AtomicReference<>();
    private static long totalBytes, networkBytes, networkAttempts;
    private CloudWorkloadTelemetry() { }
    public static void initialize(Path path) throws IOException { root = path; Files.createDirectories(path); }
    private static final class Stream {
        OutputStream out; long bytes; int part;
        void append(String name, byte[] value) throws IOException {
            if (out == null || bytes + value.length > 8L << 20) {
                if (out != null) out.close();
                AdmissionJson.require(part < 128, "stream part bound");
                Path dir = root.resolve(name); Files.createDirectories(dir);
                out = Files.newOutputStream(dir.resolve(String.format("part-%04d.jsonl", part++)), StandardOpenOption.CREATE_NEW);
                bytes = 0;
            }
            out.write(value); out.flush(); bytes += value.length;
        }
    }
    public static synchronized void record(String stream, Map<String, ?> value) {
        try {
            var row = new TreeMap<String, Object>(value);
            row.put("window", window); row.put("observedNanos", System.nanoTime());
            byte[] raw = (AdmissionJson.canonical(row) + "\n").getBytes(StandardCharsets.US_ASCII);
            AdmissionJson.require(raw.length <= 1 << 20 && (totalBytes += raw.length) <= 512L << 20, "telemetry byte bound");
            streams.computeIfAbsent(stream, ignored -> new Stream()).append(stream, raw);
        } catch (IOException error) { failure.compareAndSet(null, error); throw new UncheckedIOException(error); }
    }
    public static synchronized void network(int bytes) { networkBytes += bytes; networkAttempts++; }
    public static synchronized Map<String, Object> network() { return Map.of("bytes", networkBytes, "attempts", networkAttempts); }
    public static void sample(Supplier<Map<String, Object>> state) {
        try { record("resources", Map.of("process", PerformanceTelemetry.resources(), "runtime", state.get(), "network", network())); }
        catch (Throwable error) { failure.compareAndSet(null, error); }
    }
    public static void startSampling(Supplier<Map<String, Object>> state) {
        sampler = Executors.newSingleThreadScheduledExecutor(r -> Thread.ofPlatform().daemon().name("cloud-workload-sampler").unstarted(r));
        sampler.scheduleAtFixedRate(() -> sample(state), 0, 1, TimeUnit.SECONDS);
    }
    public static void check() { if (failure.get() != null) throw new IllegalStateException("telemetry failed", failure.get()); }
    public static Path root() { return root; }
    public static void stopSampling() throws InterruptedException {
        if (sampler != null) { sampler.shutdownNow(); AdmissionJson.require(sampler.awaitTermination(5, TimeUnit.SECONDS), "sampler cleanup"); }
        check();
    }
    public static synchronized void close() throws IOException {
        for (var stream : streams.values()) if (stream.out != null) stream.out.close();
        check();
    }
}
