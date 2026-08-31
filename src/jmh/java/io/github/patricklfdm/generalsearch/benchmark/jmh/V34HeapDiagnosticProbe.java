package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.io.IOException;
import java.lang.management.GarbageCollectorMXBean;
import java.lang.management.ManagementFactory;
import java.lang.management.MemoryPoolMXBean;
import java.lang.management.MemoryType;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.TimeUnit;
import javax.management.NotificationEmitter;
import javax.management.NotificationListener;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;

/** One bounded heap diagnostic executed in an independently configured JVM. */
public final class V34HeapDiagnosticProbe {
    private static final Field<V34DiagnosticCorpus.Document, Integer> ID =
            Field.of("id", Integer.class, V34DiagnosticCorpus.Document::id);
    private static final Field<V34DiagnosticCorpus.Document, String> CATEGORY =
            Field.of("category", String.class,
                    V34DiagnosticCorpus.Document::category);
    private static final Field<V34DiagnosticCorpus.Document, String> PRIMARY =
            Field.of("primary", String.class,
                    V34DiagnosticCorpus.Document::primary);
    private static volatile Object retentionRoot;

    private V34HeapDiagnosticProbe() {
    }

    public static void main(String[] arguments) throws Exception {
        Config config = Config.parse(arguments);
        Environment environment = Environment.capture();
        String invalid = environment.invalidReason(config.requireNoSwap());
        if (invalid != null) {
            System.out.printf(
                    "heapResult=INVALID_ENV reason=%s maxHeapBytes=%d "
                            + "physicalBytes=%d swapTotalBytes=%d swapUsedBytes=%d "
                            + "collectors=%s jvmArguments=%s%n",
                    sanitize(invalid),
                    environment.maxHeapBytes(),
                    environment.physicalBytes(),
                    environment.swapTotalBytes(),
                    environment.swapUsedBytes(),
                    environment.collectors(),
                    environment.jvmArguments()
            );
            System.exit(3);
        }

        Outcome outcome = run(config);
        System.out.printf(
                "heapResult=SUCCESS axis=%s documents=%d tokens=%d operations=%d "
                        + "maxHeapBytes=%d physicalBytes=%d swapTotalBytes=%d "
                        + "swapUsedBytes=%d collectors=%s jvmArguments=%s "
                        + "emptyUsedBytes=%d loadedUsedBytes=%d peakUsedBytes=%d "
                        + "releasedUsedBytes=%d liveSetBytes=%d allocationBytes=%d "
                        + "bytesPerOperation=%.3f gcCount=%d gcTimeMillis=%d "
                        + "gcPauseP95Millis=%d gcPauseMaxMillis=%d "
                        + "processCpuNanos=%d "
                        + "snapshotVersion=%d indexes=%d generatedTokens=%d "
                        + "resultSetCount=%d retainedCursorCount=%d checksum=%d "
                        + "corpusDigest=%s%n",
                config.axis().id(),
                config.documentCount(),
                config.tokensPerField(),
                config.operations(),
                environment.maxHeapBytes(),
                environment.physicalBytes(),
                environment.swapTotalBytes(),
                environment.swapUsedBytes(),
                environment.collectors(),
                environment.jvmArguments(),
                outcome.emptyUsedBytes(),
                outcome.loadedUsedBytes(),
                outcome.peakUsedBytes(),
                outcome.releasedUsedBytes(),
                outcome.liveSetBytes(),
                outcome.allocationBytes(),
                (double) outcome.allocationBytes() / config.operations(),
                outcome.gcCount(),
                outcome.gcTimeMillis(),
                outcome.gcPauseP95Millis(),
                outcome.gcPauseMaxMillis(),
                outcome.processCpuNanos(),
                outcome.snapshotVersion(),
                outcome.indexCount(),
                outcome.generatedTokens(),
                outcome.resultSetCount(),
                outcome.retainedCursorCount(),
                outcome.checksum(),
                outcome.corpusDigest()
        );
    }

    static Outcome run(Config config) throws Exception {
        forceGc();
        long emptyUsed = usedHeap();
        resetHeapPeaks();

        List<V34DiagnosticCorpus.Document> documents = V34DiagnosticCorpus.generate(
                new V34DiagnosticCorpus.Config(
                        config.documentCount(),
                        config.tokensPerField(),
                        config.seed(),
                        config.axis()
                ));
        String corpusDigest = V34DiagnosticCorpus.digest(documents);
        TextField<V34DiagnosticCorpus.Document> primaryText = TextField.of(
                PRIMARY,
                V34DiagnosticCorpus.analyzer(config.axis())
        );
        SearchEngine<Integer, V34DiagnosticCorpus.Document> engine = SearchEngine
                .builder(V34DiagnosticCorpus.Document.class, ID)
                .index(IndexDefinition.equality(CATEGORY))
                .index(IndexDefinition.text(primaryText))
                .build();
        boolean closed = false;
        try {
            for (int start = 0; start < documents.size(); start += 1_000) {
                engine.addAll(documents.subList(
                        start,
                        Math.min(start + 1_000, documents.size())
                )).join();
            }
            retentionRoot = List.of(documents, engine);
            forceGc();
            long loadedUsed = usedHeap();
            GcSnapshot beforeGc = GcSnapshot.capture();
            long allocatedBefore = threadAllocatedBytes();
            long cpuBefore = processCpuTime();

            SearchRequest<V34DiagnosticCorpus.Document> request = SearchRequest
                    .<V34DiagnosticCorpus.Document>builder()
                    .query(SearchQueries.phrase(primaryText, "anchor exact"))
                    .filter(Query.eq(CATEGORY, "eligible"))
                    .limit(Math.min(25, (config.documentCount() + 1) / 2))
                    .build();
            long checksum = 1L;
            GcEvents gcEvents = GcEvents.start();
            try {
                for (int operation = 0;
                        operation < config.operations();
                        operation++) {
                    List<SearchHit<V34DiagnosticCorpus.Document>> hits = engine.search(
                            request).hits();
                    if (hits.isEmpty() || hits.getFirst().document().id() != 0) {
                        throw new IllegalStateException("heap query oracle failed");
                    }
                    checksum = 31L * checksum + hits.size();
                    checksum = 31L * checksum + hits.getFirst().document().id();
                    checksum = 31L * checksum
                            + Double.doubleToRawLongBits(hits.getFirst().score());
                }
            } finally {
                gcEvents.close();
            }

            long allocatedAfter = threadAllocatedBytes();
            long cpuAfter = processCpuTime();
            GcSnapshot afterGc = GcSnapshot.capture();
            long peakUsed = peakUsedHeap();
            var metrics = engine.metrics();
            if (metrics.documentCount() != config.documentCount()
                    || metrics.registeredIndexCount() != 2
                    || checksum == 0L) {
                throw new IllegalStateException("heap final oracle failed");
            }
            long liveSet = Math.max(0L, loadedUsed - emptyUsed);
            long allocation = allocatedBefore < 0L || allocatedAfter < allocatedBefore
                    ? -1L
                    : allocatedAfter - allocatedBefore;

            engine.close();
            closed = true;
            engine = null;
            retentionRoot = null;
            documents = null;
            forceGc();
            long releasedUsed = usedHeap();
            return new Outcome(
                    emptyUsed,
                    loadedUsed,
                    peakUsed,
                    releasedUsed,
                    liveSet,
                    allocation,
                    afterGc.count() - beforeGc.count(),
                    afterGc.timeMillis() - beforeGc.timeMillis(),
                    gcEvents.p95Millis(),
                    gcEvents.maxMillis(),
                    cpuBefore < 0L || cpuAfter < cpuBefore
                            ? -1L
                            : cpuAfter - cpuBefore,
                    metrics.snapshotVersion(),
                    metrics.registeredIndexCount(),
                    Math.multiplyExact(
                            Math.multiplyExact((long) config.documentCount(), 2L),
                            config.tokensPerField() + 2L
                    ),
                    config.operations(),
                    0,
                    checksum,
                    corpusDigest
            );
        } finally {
            retentionRoot = null;
            if (!closed && engine != null) {
                engine.close();
            }
        }
    }

    private static long usedHeap() {
        return ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed();
    }

    private static long peakUsedHeap() {
        return ManagementFactory.getMemoryPoolMXBeans().stream()
                .filter(pool -> pool.getType() == MemoryType.HEAP)
                .map(MemoryPoolMXBean::getPeakUsage)
                .filter(java.util.Objects::nonNull)
                .mapToLong(usage -> usage.getUsed())
                .sum();
    }

    private static void resetHeapPeaks() {
        ManagementFactory.getMemoryPoolMXBeans().stream()
                .filter(pool -> pool.getType() == MemoryType.HEAP)
                .forEach(MemoryPoolMXBean::resetPeakUsage);
    }

    private static void forceGc() throws InterruptedException {
        for (int attempt = 0; attempt < 3; attempt++) {
            System.gc();
            TimeUnit.MILLISECONDS.sleep(25L);
        }
    }

    private static long threadAllocatedBytes() {
        java.lang.management.ThreadMXBean bean =
                ManagementFactory.getThreadMXBean();
        if (!(bean instanceof com.sun.management.ThreadMXBean allocated)
                || !allocated.isThreadAllocatedMemorySupported()) {
            return -1L;
        }
        if (!allocated.isThreadAllocatedMemoryEnabled()) {
            allocated.setThreadAllocatedMemoryEnabled(true);
        }
        return allocated.getThreadAllocatedBytes(Thread.currentThread().threadId());
    }

    private static long processCpuTime() {
        var bean = ManagementFactory.getOperatingSystemMXBean();
        if (bean instanceof com.sun.management.OperatingSystemMXBean extended) {
            return extended.getProcessCpuTime();
        }
        return -1L;
    }

    private static String sanitize(String value) {
        return value.replace(' ', '_').replace(',', '_');
    }

    record Outcome(
            long emptyUsedBytes,
            long loadedUsedBytes,
            long peakUsedBytes,
            long releasedUsedBytes,
            long liveSetBytes,
            long allocationBytes,
            long gcCount,
            long gcTimeMillis,
            long gcPauseP95Millis,
            long gcPauseMaxMillis,
            long processCpuNanos,
            long snapshotVersion,
            int indexCount,
            long generatedTokens,
            int resultSetCount,
            int retainedCursorCount,
            long checksum,
            String corpusDigest
    ) {
    }

    record Config(
            int documentCount,
            int tokensPerField,
            int operations,
            long seed,
            V34DiagnosticCorpus.Axis axis,
            boolean requireNoSwap
    ) {
        Config {
            new V34DiagnosticCorpus.Config(
                    documentCount,
                    tokensPerField,
                    seed,
                    axis
            );
            if (operations <= 0 || operations > 1_000_000) {
                throw new IllegalArgumentException(
                        "operations must be in [1, 1000000]");
            }
        }

        static Config parse(String[] arguments) {
            int documents = 100_000;
            int tokens = 16;
            int operations = 1_000;
            long seed = 34L;
            V34DiagnosticCorpus.Axis axis =
                    V34DiagnosticCorpus.Axis.SPARSE_VOCABULARY;
            boolean requireNoSwap = true;
            for (String argument : arguments) {
                if (argument.startsWith("--documents=")) {
                    documents = Integer.parseInt(argument.substring(12));
                } else if (argument.startsWith("--tokens=")) {
                    tokens = Integer.parseInt(argument.substring(9));
                } else if (argument.startsWith("--operations=")) {
                    operations = Integer.parseInt(argument.substring(13));
                } else if (argument.startsWith("--seed=")) {
                    seed = Long.parseLong(argument.substring(7));
                } else if (argument.startsWith("--axis=")) {
                    axis = V34DiagnosticCorpus.Axis.parse(argument.substring(7));
                } else if (argument.startsWith("--require-no-swap=")) {
                    requireNoSwap = strictBoolean(argument.substring(18));
                } else {
                    throw new IllegalArgumentException(
                            "unknown heap probe argument: " + argument);
                }
            }
            return new Config(
                    documents,
                    tokens,
                    operations,
                    seed,
                    axis,
                    requireNoSwap
            );
        }

        private static boolean strictBoolean(String value) {
            if (value.equals("true")) {
                return true;
            }
            if (value.equals("false")) {
                return false;
            }
            throw new IllegalArgumentException("invalid boolean: " + value);
        }
    }

    record Environment(
            long maxHeapBytes,
            long physicalBytes,
            long swapTotalBytes,
            long swapUsedBytes,
            String collectors,
            String jvmArguments
    ) {
        static Environment capture() {
            long physical = -1L;
            var os = ManagementFactory.getOperatingSystemMXBean();
            if (os instanceof com.sun.management.OperatingSystemMXBean extended) {
                physical = extended.getTotalMemorySize();
            }
            long[] swap = readSwap();
            String collectors = ManagementFactory.getGarbageCollectorMXBeans()
                    .stream()
                    .map(GarbageCollectorMXBean::getName)
                    .sorted()
                    .map(V34HeapDiagnosticProbe::sanitize)
                    .collect(java.util.stream.Collectors.joining(","));
            String arguments = ManagementFactory.getRuntimeMXBean()
                    .getInputArguments()
                    .stream()
                    .map(V34HeapDiagnosticProbe::sanitize)
                    .collect(java.util.stream.Collectors.joining(","));
            return new Environment(
                    Runtime.getRuntime().maxMemory(),
                    physical,
                    swap[0],
                    swap[1],
                    collectors.isBlank() ? "unknown" : collectors,
                    arguments.isBlank() ? "none" : arguments
            );
        }

        String invalidReason(boolean requireNoSwap) {
            if (physicalBytes <= 0L) {
                return "physical-memory-unavailable";
            }
            if (maxHeapBytes > physicalBytes) {
                return "max-heap-exceeds-physical-memory";
            }
            if (requireNoSwap && swapUsedBytes > 0L) {
                return "swap-is-in-use";
            }
            if (requireNoSwap && swapUsedBytes < 0L) {
                return "swap-state-unavailable";
            }
            return null;
        }

        private static long[] readSwap() {
            long total = -1L;
            long free = -1L;
            try {
                for (String line : Files.readAllLines(Path.of("/proc/meminfo"))) {
                    if (line.startsWith("SwapTotal:")) {
                        total = kibibytes(line);
                    } else if (line.startsWith("SwapFree:")) {
                        free = kibibytes(line);
                    }
                }
            } catch (IOException ignored) {
                return new long[]{-1L, -1L};
            }
            return new long[]{total, total < 0L || free < 0L ? -1L : total - free};
        }

        private static long kibibytes(String line) {
            String[] parts = line.trim().split("\\s+");
            return Math.multiplyExact(Long.parseLong(parts[1]), 1_024L);
        }
    }

    record GcSnapshot(long count, long timeMillis) {
        static GcSnapshot capture() {
            long count = 0L;
            long time = 0L;
            for (GarbageCollectorMXBean bean
                    : ManagementFactory.getGarbageCollectorMXBeans()) {
                count += Math.max(0L, bean.getCollectionCount());
                time += Math.max(0L, bean.getCollectionTime());
            }
            return new GcSnapshot(count, time);
        }
    }

    private static final class GcEvents implements AutoCloseable {
        private final List<Long> durations = new java.util.concurrent.CopyOnWriteArrayList<>();
        private final List<Registration> registrations = new java.util.ArrayList<>();

        static GcEvents start() {
            GcEvents events = new GcEvents();
            for (GarbageCollectorMXBean bean
                    : ManagementFactory.getGarbageCollectorMXBeans()) {
                if (bean instanceof NotificationEmitter emitter) {
                    NotificationListener listener = (notification, ignored) -> {
                        if (notification.getType().equals(
                                com.sun.management.GarbageCollectionNotificationInfo
                                        .GARBAGE_COLLECTION_NOTIFICATION)) {
                            var info = com.sun.management
                                    .GarbageCollectionNotificationInfo.from(
                                            (javax.management.openmbean.CompositeData)
                                                    notification.getUserData());
                            events.durations.add(
                                    info.getGcInfo().getDuration());
                        }
                    };
                    emitter.addNotificationListener(listener, null, null);
                    events.registrations.add(new Registration(emitter, listener));
                }
            }
            return events;
        }

        long p95Millis() {
            if (durations.isEmpty()) {
                return 0L;
            }
            long[] sorted = durations.stream().mapToLong(Long::longValue)
                    .sorted().toArray();
            int index = Math.max(0,
                    (int) Math.ceil(sorted.length * 0.95) - 1);
            return sorted[index];
        }

        long maxMillis() {
            return durations.stream().mapToLong(Long::longValue).max().orElse(0L);
        }

        @Override
        public void close() {
            for (Registration registration : registrations) {
                try {
                    registration.emitter().removeNotificationListener(
                            registration.listener());
                } catch (javax.management.ListenerNotFoundException impossible) {
                    throw new IllegalStateException(impossible);
                }
            }
        }

        private record Registration(
                NotificationEmitter emitter,
                NotificationListener listener
        ) {
        }
    }
}
