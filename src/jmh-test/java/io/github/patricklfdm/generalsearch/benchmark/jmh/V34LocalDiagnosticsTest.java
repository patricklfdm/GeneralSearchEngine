package io.github.patricklfdm.generalsearch.benchmark.jmh;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class V34LocalDiagnosticsTest {
    @Test
    void corpusIsBoundedDeterministicAndSeedSensitiveWhereDeclared() {
        var first = new V34DiagnosticCorpus.Config(
                12,
                8,
                34L,
                V34DiagnosticCorpus.Axis.LARGE_VOCABULARY
        );
        var second = new V34DiagnosticCorpus.Config(
                12,
                8,
                35L,
                V34DiagnosticCorpus.Axis.LARGE_VOCABULARY
        );

        String firstDigest = V34DiagnosticCorpus.digest(
                V34DiagnosticCorpus.generate(first));
        assertEquals(firstDigest, V34DiagnosticCorpus.digest(
                V34DiagnosticCorpus.generate(first)));
        assertNotEquals(firstDigest, V34DiagnosticCorpus.digest(
                V34DiagnosticCorpus.generate(second)));
        assertEquals(List.of(0, 2, 4, 6, 8, 10),
                V34DiagnosticCorpus.expectedEligibleIds(12));

        assertThrows(IllegalArgumentException.class, () ->
                new V34DiagnosticCorpus.Config(
                        V34DiagnosticCorpus.MAX_DOCUMENTS + 1,
                        8,
                        34L,
                        V34DiagnosticCorpus.Axis.LONG_TEXT));
        assertThrows(IllegalArgumentException.class, () ->
                new V34DiagnosticCorpus.Config(
                        1,
                        V34DiagnosticCorpus.MAX_TOKENS_PER_FIELD + 1,
                        34L,
                        V34DiagnosticCorpus.Axis.LONG_TEXT));
    }

    @Test
    void everyExtremeAxisPassesTheReducedIndependentOracle() {
        for (V34DiagnosticCorpus.Axis axis : V34DiagnosticCorpus.Axis.values()) {
            var config = new V34DiagnosticCorpus.Config(20, 8, 34L, axis);
            var first = V34ExtremeCorpusProbe.run(config);
            var second = V34ExtremeCorpusProbe.run(config);

            assertEquals(10, first.matchCount(), axis.id());
            assertEquals(first, second, axis.id());
            assertNotEquals(0L, first.combinedChecksum(), axis.id());
        }
    }

    @Test
    void coldRunnerRequiresEveryOrderedCheckpointAndNonZeroChecksum() {
        List<String> output = validColdOutput();
        var outcome = V34ColdBuildProcessRunner.evaluate(false, 0, output);

        assertEquals(V34ColdBuildProcessRunner.Status.SUCCESS, outcome.status());
        assertEquals(6L, outcome.readyNanos());
        assertEquals(10L, outcome.totalNanos());
        assertEquals(41L, outcome.checksum());
        assertEquals("a".repeat(64), outcome.corpusDigest());

        List<String> missing = new ArrayList<>(output);
        missing.remove(3);
        assertEquals(V34ColdBuildProcessRunner.Status.MISSING_CHECKPOINT,
                V34ColdBuildProcessRunner.evaluate(false, 0, missing).status());

        List<String> reordered = new ArrayList<>(output);
        String first = reordered.get(0);
        reordered.set(0, reordered.get(1));
        reordered.set(1, first);
        assertEquals(V34ColdBuildProcessRunner.Status.MISSING_CHECKPOINT,
                V34ColdBuildProcessRunner.evaluate(false, 0, reordered).status());

        List<String> zeroChecksum = new ArrayList<>(output);
        zeroChecksum.set(zeroChecksum.size() - 1,
                "result=SUCCESS checksum=0 corpusDigest=" + "a".repeat(64));
        assertEquals(V34ColdBuildProcessRunner.Status.INVALID_OUTPUT,
                V34ColdBuildProcessRunner.evaluate(
                        false, 0, zeroChecksum).status());

        List<String> duplicateResult = new ArrayList<>(output);
        duplicateResult.add("result=SUCCESS checksum=41 corpusDigest="
                + "a".repeat(64));
        assertEquals(V34ColdBuildProcessRunner.Status.INVALID_OUTPUT,
                V34ColdBuildProcessRunner.evaluate(
                        false, 0, duplicateResult).status());
    }

    @Test
    void coldRunnerClassifiesTimeoutFailureAndExhaustion() {
        assertEquals(V34ColdBuildProcessRunner.Status.TIMEOUT,
                V34ColdBuildProcessRunner.evaluate(true, -1, List.of()).status());
        assertEquals(V34ColdBuildProcessRunner.Status.NON_ZERO_EXIT,
                V34ColdBuildProcessRunner.evaluate(
                        false, 2, List.of("failure")).status());
        assertEquals(V34ColdBuildProcessRunner.Status.RESOURCE_EXHAUSTED,
                V34ColdBuildProcessRunner.evaluate(
                        false,
                        1,
                        List.of("java.lang.OutOfMemoryError: Java heap space")
                ).status());
    }

    @Test
    void heapRunnerRejectsPartialAndInvalidEvidence() {
        String success = validHeapOutput();
        assertEquals(V34HeapMatrixRunner.Status.SUCCESS,
                V34HeapMatrixRunner.evaluate(
                        false, 0, List.of(success)).status());
        assertEquals(V34HeapMatrixRunner.Status.INVALID_OUTPUT,
                V34HeapMatrixRunner.evaluate(
                        false, 0, List.of("heapResult=SUCCESS checksum=41"))
                        .status());
        assertEquals(V34HeapMatrixRunner.Status.INVALID_ENVIRONMENT,
                V34HeapMatrixRunner.evaluate(
                        false,
                        3,
                        List.of("heapResult=INVALID_ENV reason=swap-is-in-use")
                ).status());
        assertEquals(V34HeapMatrixRunner.Status.RESOURCE_EXHAUSTED,
                V34HeapMatrixRunner.evaluate(
                        false,
                        1,
                        List.of("OutOfMemoryError: Java heap space")
                ).status());
        assertEquals(V34HeapMatrixRunner.Status.MISSING_RESULT,
                V34HeapMatrixRunner.evaluate(false, 0, List.of("partial")).status());
        assertEquals(V34HeapMatrixRunner.Status.TIMEOUT,
                V34HeapMatrixRunner.evaluate(true, -1, List.of()).status());
        assertEquals(V34HeapMatrixRunner.Status.INVALID_OUTPUT,
                V34HeapMatrixRunner.evaluate(
                        false, 0, List.of(success, success)).status());
    }

    @Test
    void heapEnvironmentAndParsersFailClosed() {
        var tooLarge = new V34HeapDiagnosticProbe.Environment(
                3_000L, 2_000L, 0L, 0L, "G1", "-Xmx3g");
        var swapped = new V34HeapDiagnosticProbe.Environment(
                1_000L, 2_000L, 2_000L, 1L, "G1", "-Xmx1g");

        assertEquals("max-heap-exceeds-physical-memory",
                tooLarge.invalidReason(true));
        assertEquals("swap-is-in-use", swapped.invalidReason(true));
        assertEquals(null, swapped.invalidReason(false));
        assertThrows(IllegalArgumentException.class, () ->
                V34HeapMatrixRunner.Config.parse(new String[]{"--heaps=0g"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34HeapMatrixRunner.Config.parse(
                        new String[]{"--require-no-swap=True"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34HeapDiagnosticProbe.Config.parse(
                        new String[]{"--operations=0"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34ExtremeCorpusProbe.Config.parse(
                        new String[]{"--axis=unknown"}));

        var maximum = new V34DiagnosticCorpus.Config(
                1,
                V34DiagnosticCorpus.MAX_TOKENS_PER_FIELD,
                34L,
                V34DiagnosticCorpus.Axis.LONG_TEXT
        );
        assertEquals(1, V34DiagnosticCorpus.generate(maximum).size());
    }

    private static List<String> validColdOutput() {
        List<String> output = new ArrayList<>();
        int elapsed = 0;
        for (V34ColdBuildProbe.Checkpoint checkpoint
                : V34ColdBuildProbe.Checkpoint.values()) {
            output.add("checkpoint=" + checkpoint.name()
                    + " elapsedNanos=" + elapsed++);
        }
        output.add("result=SUCCESS checksum=41 corpusDigest=" + "a".repeat(64));
        assertTrue(output.size() > 1);
        return output;
    }

    private static String validHeapOutput() {
        return "heapResult=SUCCESS axis=sparse-vocabulary documents=10 "
                + "tokens=8 operations=10 maxHeapBytes=1024 physicalBytes=2048 "
                + "collectors=G1 jvmArguments=-Xmx1g emptyUsedBytes=1 "
                + "loadedUsedBytes=2 peakUsedBytes=3 releasedUsedBytes=1 "
                + "liveSetBytes=1 allocationBytes=4 bytesPerOperation=0.4 "
                + "gcCount=0 gcTimeMillis=0 gcPauseP95Millis=0 "
                + "gcPauseMaxMillis=0 processCpuNanos=1 snapshotVersion=1 "
                + "indexes=2 generatedTokens=10 resultSetCount=10 "
                + "retainedCursorCount=0 checksum=-41 corpusDigest="
                + "a".repeat(64);
    }
}
