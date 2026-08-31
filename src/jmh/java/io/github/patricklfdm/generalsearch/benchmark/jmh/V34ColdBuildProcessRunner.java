package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/** Repeats the cold-build probe in independent JVMs and rejects partial evidence. */
public final class V34ColdBuildProcessRunner {
    private V34ColdBuildProcessRunner() {
    }

    public static void main(String[] arguments) throws Exception {
        Config config = Config.parse(arguments);
        List<RunOutcome> outcomes = new ArrayList<>(config.repeats());
        for (int run = 0; run < config.repeats(); run++) {
            RunOutcome outcome = run(config);
            outcomes.add(outcome);
            System.out.printf(
                    "coldRun=%d status=%s processReadyNanos=%d "
                            + "probeReadyNanos=%d processTotalNanos=%d "
                            + "probeTotalNanos=%d "
                            + "checksum=%d detail=%s%n",
                    run + 1,
                    outcome.status(),
                    outcome.processReadyNanos(),
                    outcome.readyNanos(),
                    outcome.processTotalNanos(),
                    outcome.totalNanos(),
                    outcome.checksum(),
                    sanitize(outcome.detail())
            );
            if (outcome.status() != Status.SUCCESS) {
                throw new IllegalStateException(
                        "cold-build run " + (run + 1) + " failed: " + outcome);
            }
        }

        long[] ready = outcomes.stream().mapToLong(RunOutcome::readyNanos).sorted()
                .toArray();
        long[] total = outcomes.stream().mapToLong(RunOutcome::totalNanos).sorted()
                .toArray();
        long[] processReady = outcomes.stream()
                .mapToLong(RunOutcome::processReadyNanos).sorted().toArray();
        long[] processTotal = outcomes.stream()
                .mapToLong(RunOutcome::processTotalNanos).sorted().toArray();
        long checksum = outcomes.getFirst().checksum();
        String corpusDigest = outcomes.getFirst().corpusDigest();
        if (outcomes.stream().anyMatch(outcome -> outcome.checksum() != checksum)) {
            throw new IllegalStateException(
                    "cold-build checksum changed across independent processes");
        }
        if (outcomes.stream().anyMatch(outcome ->
                !outcome.corpusDigest().equals(corpusDigest))) {
            throw new IllegalStateException(
                    "cold-build corpus digest changed across independent processes");
        }
        System.out.printf(
                "coldSummary=SUCCESS repeats=%d documents=%d readyMedianNanos=%d "
                        + "readyCv=%.6f totalMedianNanos=%d totalCv=%.6f "
                        + "processReadyMedianNanos=%d processReadyCv=%.6f "
                        + "processTotalMedianNanos=%d processTotalCv=%.6f "
                        + "checksum=%d corpusDigest=%s%n",
                config.repeats(),
                config.documentCount(),
                median(ready),
                coefficientOfVariation(ready),
                median(total),
                coefficientOfVariation(total),
                median(processReady),
                coefficientOfVariation(processReady),
                median(processTotal),
                coefficientOfVariation(processTotal),
                checksum,
                corpusDigest
        );
    }

    static RunOutcome evaluate(
            boolean timedOut,
            int exitCode,
            List<String> output
    ) {
        if (timedOut) {
            return RunOutcome.failed(Status.TIMEOUT, "process timed out");
        }
        if (exitCode != 0) {
            if (output.stream().anyMatch(line ->
                    line.contains("OutOfMemoryError")
                            || line.contains("Cannot reserve enough space"))) {
                return RunOutcome.failed(
                        Status.RESOURCE_EXHAUSTED,
                        "exit=" + exitCode + ":" + String.join("|", output)
                );
            }
            return RunOutcome.failed(
                    Status.NON_ZERO_EXIT,
                    "exit=" + exitCode + ":" + String.join("|", output)
            );
        }

        List<V34ColdBuildProbe.Checkpoint> checkpoints = new ArrayList<>();
        Map<V34ColdBuildProbe.Checkpoint, Long> elapsed =
                new EnumMap<>(V34ColdBuildProbe.Checkpoint.class);
        Long checksum = null;
        String corpusDigest = null;
        int resultCount = 0;
        for (String line : output) {
            if (line.startsWith("checkpoint=")) {
                Map<String, String> fields = fields(line);
                try {
                    V34ColdBuildProbe.Checkpoint checkpoint =
                            V34ColdBuildProbe.Checkpoint.valueOf(
                                    fields.get("checkpoint"));
                    checkpoints.add(checkpoint);
                    elapsed.put(checkpoint,
                            Long.parseLong(fields.get("elapsedNanos")));
                } catch (RuntimeException invalid) {
                    return RunOutcome.failed(
                            Status.INVALID_OUTPUT,
                            "invalid checkpoint: " + line
                    );
                }
            } else if (line.startsWith("result=SUCCESS")) {
                resultCount++;
                try {
                    checksum = Long.parseLong(fields(line).get("checksum"));
                    corpusDigest = fields(line).get("corpusDigest");
                } catch (RuntimeException invalid) {
                    return RunOutcome.failed(
                            Status.INVALID_OUTPUT,
                            "invalid result: " + line
                    );
                }
            }
        }

        List<V34ColdBuildProbe.Checkpoint> expected =
                List.of(V34ColdBuildProbe.Checkpoint.values());
        if (resultCount > 1) {
            return RunOutcome.failed(
                    Status.INVALID_OUTPUT,
                    "multiple success results"
            );
        }
        if (!checkpoints.equals(expected)
                || checksum == null
                || corpusDigest == null
                || resultCount == 0) {
            return RunOutcome.failed(
                    Status.MISSING_CHECKPOINT,
                    "expected=" + expected + ",actual=" + checkpoints
            );
        }
        if (checksum == 0L || !corpusDigest.matches("[0-9a-f]{64}")) {
            return RunOutcome.failed(
                    Status.INVALID_OUTPUT,
                    "invalid result identity"
            );
        }
        long previous = -1L;
        for (V34ColdBuildProbe.Checkpoint checkpoint : expected) {
            long current = elapsed.get(checkpoint);
            if (current < 0L || current < previous) {
                return RunOutcome.failed(
                        Status.INVALID_OUTPUT,
                        "non-monotonic checkpoint time at " + checkpoint
                );
            }
            previous = current;
        }
        return new RunOutcome(
                Status.SUCCESS,
                elapsed.get(V34ColdBuildProbe.Checkpoint.READY_TO_SEARCH),
                elapsed.get(V34ColdBuildProbe.Checkpoint.CLOSED),
                -1L,
                -1L,
                checksum,
                corpusDigest,
                "ok"
        );
    }

    private static RunOutcome run(Config config) throws Exception {
        List<String> command = List.of(
                javaBinary().toString(),
                "-cp",
                config.classpath(),
                V34ColdBuildProbe.class.getName(),
                "--documents=" + config.documentCount(),
                "--tokens=" + config.tokensPerField(),
                "--batch-size=" + config.batchSize(),
                "--seed=" + config.seed()
        );
        long processStart = System.nanoTime();
        Process process = new ProcessBuilder(command)
                .redirectErrorStream(true)
                .start();
        List<String> output = java.util.Collections.synchronizedList(
                new ArrayList<>());
        AtomicLong processReady = new AtomicLong(-1L);
        Thread outputReader = Thread.ofVirtual().start(() -> {
            try (var reader = process.inputReader()) {
                reader.lines().forEach(line -> {
                    output.add(line);
                    if (line.startsWith("checkpoint=READY_TO_SEARCH ")) {
                        processReady.compareAndSet(
                                -1L,
                                System.nanoTime() - processStart
                        );
                    }
                });
            } catch (IOException failure) {
                output.add("runnerReadFailure=" + failure.getClass().getName());
            }
        });
        boolean completed = process.waitFor(
                config.timeout().toMillis(),
                TimeUnit.MILLISECONDS
        );
        if (!completed) {
            process.destroyForcibly();
            process.waitFor(10, TimeUnit.SECONDS);
        }
        long processTotal = System.nanoTime() - processStart;
        outputReader.join(TimeUnit.SECONDS.toMillis(10));
        if (outputReader.isAlive()) {
            return RunOutcome.failed(
                    Status.INVALID_OUTPUT,
                    "output reader did not terminate"
            );
        }
        RunOutcome evaluated = evaluate(
                !completed,
                completed ? process.exitValue() : -1,
                List.copyOf(output)
        );
        if (evaluated.status() != Status.SUCCESS) {
            return evaluated;
        }
        if (processReady.get() <= 0L || processTotal < processReady.get()) {
            return RunOutcome.failed(
                    Status.INVALID_OUTPUT,
                    "invalid parent process timing"
            );
        }
        return evaluated.withProcessTimes(processReady.get(), processTotal);
    }

    private static Map<String, String> fields(String line) {
        Map<String, String> fields = new java.util.HashMap<>();
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

    private static long median(long[] sorted) {
        int middle = sorted.length / 2;
        if ((sorted.length & 1) == 1) {
            return sorted[middle];
        }
        return Math.addExact(sorted[middle - 1], sorted[middle]) / 2L;
    }

    private static double coefficientOfVariation(long[] values) {
        double mean = Arrays.stream(values).average().orElseThrow();
        double squared = 0.0;
        for (long value : values) {
            double delta = value - mean;
            squared += delta * delta;
        }
        return mean == 0.0 ? 0.0 : Math.sqrt(squared / values.length) / mean;
    }

    private static String sanitize(String value) {
        return value.replace(' ', '_').replace('\n', '_');
    }

    enum Status {
        SUCCESS,
        TIMEOUT,
        NON_ZERO_EXIT,
        RESOURCE_EXHAUSTED,
        MISSING_CHECKPOINT,
        INVALID_OUTPUT
    }

    record RunOutcome(
            Status status,
            long readyNanos,
            long totalNanos,
            long processReadyNanos,
            long processTotalNanos,
            long checksum,
            String corpusDigest,
            String detail
    ) {
        static RunOutcome failed(Status status, String detail) {
            return new RunOutcome(
                    status, -1L, -1L, -1L, -1L, 0L, "", detail);
        }

        RunOutcome withProcessTimes(long processReady, long processTotal) {
            return new RunOutcome(
                    status,
                    readyNanos,
                    totalNanos,
                    processReady,
                    processTotal,
                    checksum,
                    corpusDigest,
                    detail
            );
        }
    }

    record Config(
            int documentCount,
            int tokensPerField,
            int batchSize,
            int repeats,
            long seed,
            Duration timeout,
            String classpath
    ) {
        Config {
            new V34ColdBuildProbe.Config(
                    documentCount,
                    tokensPerField,
                    batchSize,
                    seed
            );
            if (repeats <= 0 || repeats > 20) {
                throw new IllegalArgumentException("repeats must be in [1, 20]");
            }
            if (timeout.isNegative() || timeout.isZero()
                    || timeout.compareTo(Duration.ofHours(1)) > 0) {
                throw new IllegalArgumentException("invalid timeout");
            }
            if (classpath == null || classpath.isBlank()) {
                throw new IllegalArgumentException("classpath must not be blank");
            }
        }

        static Config parse(String[] arguments) {
            int documents = 100_000;
            int tokens = 16;
            int batch = 1_000;
            int repeats = 5;
            long seed = 34L;
            long timeoutSeconds = 600L;
            String classpath = System.getProperty("java.class.path");
            for (String argument : arguments) {
                if (argument.startsWith("--documents=")) {
                    documents = Integer.parseInt(argument.substring(12));
                } else if (argument.startsWith("--tokens=")) {
                    tokens = Integer.parseInt(argument.substring(9));
                } else if (argument.startsWith("--batch-size=")) {
                    batch = Integer.parseInt(argument.substring(13));
                } else if (argument.startsWith("--repeats=")) {
                    repeats = Integer.parseInt(argument.substring(10));
                } else if (argument.startsWith("--seed=")) {
                    seed = Long.parseLong(argument.substring(7));
                } else if (argument.startsWith("--timeout-seconds=")) {
                    timeoutSeconds = Long.parseLong(argument.substring(18));
                } else if (argument.startsWith("--classpath=")) {
                    classpath = argument.substring(12);
                } else {
                    throw new IllegalArgumentException(
                            "unknown cold runner argument: " + argument);
                }
            }
            return new Config(
                    documents,
                    tokens,
                    batch,
                    repeats,
                    seed,
                    Duration.ofSeconds(timeoutSeconds),
                    classpath
            );
        }
    }
}
