package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/** Launches bounded heap diagnostics as independent, explicitly sized JVMs. */
public final class V34HeapMatrixRunner {
    private V34HeapMatrixRunner() {
    }

    public static void main(String[] arguments) throws Exception {
        Config config = Config.parse(arguments);
        boolean passed = true;
        for (String heap : config.heaps()) {
            Cell cell = run(config, heap);
            System.out.printf(
                    "heapCell=%s status=%s exitCode=%d detail=%s%n",
                    heap,
                    cell.status(),
                    cell.exitCode(),
                    sanitize(cell.detail())
            );
            passed &= cell.status() == Status.SUCCESS;
        }
        System.out.printf(
                "heapMatrix=%s cells=%d documents=%d tokens=%d operations=%d%n",
                passed ? "SUCCESS" : "NON_PASSING",
                config.heaps().size(),
                config.documentCount(),
                config.tokensPerField(),
                config.operations()
        );
        if (!passed) {
            throw new IllegalStateException("one or more heap cells did not pass");
        }
    }

    static Cell evaluate(boolean timedOut, int exitCode, List<String> output) {
        if (timedOut) {
            return new Cell(Status.TIMEOUT, -1, "process timed out");
        }
        List<String> results = output.stream()
                .filter(line -> line.startsWith("heapResult="))
                .toList();
        if (results.size() > 1) {
            return new Cell(
                    Status.INVALID_OUTPUT,
                    exitCode,
                    "multiple heap results"
            );
        }
        String result = results.isEmpty() ? null : results.getFirst();
        if (result != null) {
            Map<String, String> fields = fields(result);
            if ("SUCCESS".equals(fields.get("heapResult"))) {
                if (exitCode != 0
                        || !hasPositiveLong(fields, "maxHeapBytes")
                        || !hasPositiveLong(fields, "physicalBytes")
                        || !hasPositiveLong(fields, "operations")
                        || !hasNonZeroLong(fields, "checksum")
                        || !completeSuccess(fields)) {
                    return new Cell(Status.INVALID_OUTPUT, exitCode, result);
                }
                return new Cell(Status.SUCCESS, exitCode, result);
            }
            if ("INVALID_ENV".equals(fields.get("heapResult"))) {
                return new Cell(Status.INVALID_ENVIRONMENT, exitCode, result);
            }
        }
        if (output.stream().anyMatch(line -> line.contains("OutOfMemoryError"))) {
            return new Cell(Status.RESOURCE_EXHAUSTED, exitCode,
                    String.join("|", output));
        }
        if (exitCode != 0) {
            return new Cell(Status.NON_ZERO_EXIT, exitCode,
                    String.join("|", output));
        }
        return new Cell(Status.MISSING_RESULT, exitCode, String.join("|", output));
    }

    private static Cell run(Config config, String heap) throws Exception {
        List<String> command = List.of(
                javaBinary().toString(),
                "-Xms" + heap,
                "-Xmx" + heap,
                "-XX:+UseG1GC",
                "-cp",
                config.classpath(),
                V34HeapDiagnosticProbe.class.getName(),
                "--documents=" + config.documentCount(),
                "--tokens=" + config.tokensPerField(),
                "--operations=" + config.operations(),
                "--seed=" + config.seed(),
                "--axis=" + config.axis().id(),
                "--require-no-swap=" + config.requireNoSwap()
        );
        Process process = new ProcessBuilder(command)
                .redirectErrorStream(true)
                .start();
        boolean completed = process.waitFor(
                config.timeout().toMillis(),
                TimeUnit.MILLISECONDS
        );
        if (!completed) {
            process.destroyForcibly();
            process.waitFor(10, TimeUnit.SECONDS);
        }
        List<String> output;
        try (var reader = process.inputReader()) {
            output = reader.lines().toList();
        }
        return evaluate(!completed, completed ? process.exitValue() : -1, output);
    }

    private static boolean hasPositiveLong(
            Map<String, String> fields,
            String key
    ) {
        try {
            return Long.parseLong(fields.get(key)) > 0L;
        } catch (RuntimeException invalid) {
            return false;
        }
    }

    private static boolean hasNonZeroLong(
            Map<String, String> fields,
            String key
    ) {
        try {
            return Long.parseLong(fields.get(key)) != 0L;
        } catch (RuntimeException invalid) {
            return false;
        }
    }

    private static boolean completeSuccess(Map<String, String> fields) {
        List<String> required = List.of(
                "axis",
                "documents",
                "tokens",
                "emptyUsedBytes",
                "loadedUsedBytes",
                "peakUsedBytes",
                "releasedUsedBytes",
                "liveSetBytes",
                "allocationBytes",
                "bytesPerOperation",
                "gcCount",
                "gcTimeMillis",
                "gcPauseP95Millis",
                "gcPauseMaxMillis",
                "processCpuNanos",
                "snapshotVersion",
                "indexes",
                "generatedTokens",
                "resultSetCount",
                "retainedCursorCount",
                "corpusDigest",
                "collectors",
                "jvmArguments"
        );
        if (!fields.keySet().containsAll(required)
                || !fields.get("corpusDigest").matches("[0-9a-f]{64}")) {
            return false;
        }
        try {
            Double.parseDouble(fields.get("bytesPerOperation"));
            for (String field : List.of(
                    "documents",
                    "tokens",
                    "emptyUsedBytes",
                    "loadedUsedBytes",
                    "peakUsedBytes",
                    "releasedUsedBytes",
                    "liveSetBytes",
                    "allocationBytes",
                    "gcCount",
                    "gcTimeMillis",
                    "gcPauseP95Millis",
                    "gcPauseMaxMillis",
                    "processCpuNanos",
                    "snapshotVersion",
                    "indexes",
                    "generatedTokens",
                    "resultSetCount",
                    "retainedCursorCount")) {
                Long.parseLong(fields.get(field));
            }
            return true;
        } catch (RuntimeException invalid) {
            return false;
        }
    }

    private static Map<String, String> fields(String line) {
        Map<String, String> fields = new HashMap<>();
        for (String field : line.split(" ")) {
            int separator = field.indexOf('=');
            if (separator > 0) {
                fields.put(
                        field.substring(0, separator),
                        field.substring(separator + 1)
                );
            }
        }
        return Map.copyOf(fields);
    }

    private static Path javaBinary() {
        return Path.of(System.getProperty("java.home"), "bin", "java");
    }

    private static String sanitize(String value) {
        return value.replace(' ', '_').replace('\n', '_');
    }

    enum Status {
        SUCCESS,
        INVALID_ENVIRONMENT,
        RESOURCE_EXHAUSTED,
        TIMEOUT,
        NON_ZERO_EXIT,
        MISSING_RESULT,
        INVALID_OUTPUT
    }

    record Cell(Status status, int exitCode, String detail) {
    }

    record Config(
            List<String> heaps,
            int documentCount,
            int tokensPerField,
            int operations,
            long seed,
            V34DiagnosticCorpus.Axis axis,
            boolean requireNoSwap,
            Duration timeout,
            String classpath
    ) {
        Config {
            heaps = List.copyOf(heaps);
            if (heaps.isEmpty() || heaps.size() > 8) {
                throw new IllegalArgumentException("heap matrix must have 1-8 cells");
            }
            for (String heap : heaps) {
                if (!heap.matches("[1-9][0-9]*[mg]")) {
                    throw new IllegalArgumentException("invalid heap size: " + heap);
                }
            }
            new V34HeapDiagnosticProbe.Config(
                    documentCount,
                    tokensPerField,
                    operations,
                    seed,
                    axis,
                    requireNoSwap
            );
            if (timeout.isZero() || timeout.isNegative()
                    || timeout.compareTo(Duration.ofHours(1)) > 0) {
                throw new IllegalArgumentException("invalid timeout");
            }
            if (classpath == null || classpath.isBlank()) {
                throw new IllegalArgumentException("classpath must not be blank");
            }
        }

        static Config parse(String[] arguments) {
            List<String> heaps = List.of("4g", "8g", "16g");
            int documents = 100_000;
            int tokens = 16;
            int operations = 1_000;
            long seed = 34L;
            V34DiagnosticCorpus.Axis axis =
                    V34DiagnosticCorpus.Axis.SPARSE_VOCABULARY;
            boolean requireNoSwap = true;
            long timeoutSeconds = 600L;
            String classpath = System.getProperty("java.class.path");
            for (String argument : arguments) {
                if (argument.startsWith("--heaps=")) {
                    heaps = List.of(argument.substring(8)
                            .toLowerCase(Locale.ROOT).split(","));
                } else if (argument.startsWith("--documents=")) {
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
                } else if (argument.startsWith("--timeout-seconds=")) {
                    timeoutSeconds = Long.parseLong(argument.substring(18));
                } else if (argument.startsWith("--classpath=")) {
                    classpath = argument.substring(12);
                } else {
                    throw new IllegalArgumentException(
                            "unknown heap runner argument: " + argument);
                }
            }
            return new Config(
                    heaps,
                    documents,
                    tokens,
                    operations,
                    seed,
                    axis,
                    requireNoSwap,
                    Duration.ofSeconds(timeoutSeconds),
                    classpath
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
}
