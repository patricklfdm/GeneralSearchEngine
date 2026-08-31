package io.github.patricklfdm.generalsearch.benchmark.jmh;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V34Phase3DiagnosticsTest {
    @Test
    void burstMatrixIsBoundedAndAtomicObservationsAreStrict() {
        var defaults = V34BurstRecoveryProbe.Config.parse(new String[0]);
        assertEquals(List.of(1, 4, 16), defaults.producerCounts());
        assertEquals(List.of(1, 100, 1_000), defaults.batchSizes());
        assertTrue(V34BurstRecoveryProbe.atomicObservation(0, 100));
        assertTrue(V34BurstRecoveryProbe.atomicObservation(100, 100));
        assertFalse(V34BurstRecoveryProbe.atomicObservation(1, 100));

        assertThrows(IllegalArgumentException.class, () ->
                V34BurstRecoveryProbe.Config.parse(new String[]{
                        "--producers=1,1"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34BurstRecoveryProbe.Config.parse(new String[]{
                        "--batch-sizes=1001"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34BurstRecoveryProbe.Config.parse(new String[]{
                        "--producers=16", "--batch-sizes=1000",
                        "--batches-per-producer=2", "--documents=1000"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34BurstRecoveryProbe.Config.parse(new String[]{
                        "--unknown=1"}));
    }

    @Test
    void reducedBurstCellCompletesEveryFutureAndFinalOracle() throws Exception {
        var config = new V34BurstRecoveryProbe.Config(
                List.of(2), List.of(5), 2, 100, 2, 8, 30);
        var result = V34BurstRecoveryProbe.runCell(config, 2, 5);

        assertEquals(4, result.submittedBatches());
        assertEquals(20, result.submittedMutations());
        assertEquals(0, result.unexpectedFailures());
        assertEquals(0, result.unresolvedFutures());
        assertEquals(3, result.expectedFailures());
        assertTrue(result.successfulBatches() > 0);
        assertTrue(result.readerOperations() > 0);
        assertTrue(result.snapshotDelta() > 0);
        assertEquals(64, result.corpusDigest().length());
    }

    @Test
    void longRunParserRejectsUnboundedAndAmbiguousInputs() {
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--seconds=7200"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--seconds=6", "--window-seconds=4"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--seconds=6", "--seconds=6"}));
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--paid-cloud=true"}));
    }

    @Test
    void windowGateRequiresProgressCoverageAndMonotonicEvidence() {
        var first = window(0, 10L, 100L, 110L, 0L);
        var second = window(1, 12L, 111L, 125L, 0L);
        var passing = V34LongRunCalibration.evaluateWindows(
                List.of(first, second));
        assertTrue(passing.passed(), passing.reasons().toString());
        assertEquals(10L, passing.medianReadOperations());
        assertTrue(passing.readOperationsLowerReviewBand() > 0L);
        assertTrue(passing.readP99UpperReviewBandNanos() > 0L);

        var failed = V34LongRunCalibration.evaluateWindows(List.of(
                first,
                window(1, 0L, 90L, 90L, 1L)));
        assertFalse(failed.passed());
        assertTrue(failed.reasons().stream().anyMatch(reason ->
                reason.contains("no-progress")));
        assertTrue(failed.reasons().stream().anyMatch(reason ->
                reason.contains("errors")));
        assertTrue(failed.reasons().stream().anyMatch(reason ->
                reason.contains("snapshot-invalid")));
    }

    @Test
    void forkEquivalentReducedLongRunWritesCompleteArtifacts(
            @TempDir Path output
    ) throws Exception {
        V34LongRunCalibration.main(new String[]{
                "--output=" + output,
                "--documents=100",
                "--readers=6",
                "--seconds=2",
                "--warmup-seconds=0",
                "--window-seconds=1",
                "--sample-millis=250",
                "--top-k=10",
                "--steady-millis=20",
                "--burst-every-seconds=1",
                "--burst-producers=2",
                "--burst-batch-size=5",
                "--lifecycle-every-seconds=1",
                "--queue-capacity=32",
                "--source-commit=test-fixture",
                "--tree-state=clean"
        });

        for (String name : List.of(
                "config.properties", "samples.csv", "windows.csv",
                "summary.properties", "manifest.sha256")) {
            assertTrue(Files.size(output.resolve(name)) > 0L, name);
        }
        assertFalse(Files.exists(output.resolve("failure.txt")));
        assertTrue(Files.readString(output.resolve("summary.properties"))
                .contains("status=SUCCESS"));
        assertEquals(4, Files.readAllLines(
                output.resolve("manifest.sha256")).size());
    }

    private static V34LongRunCalibration.WindowResult window(
            int index,
            long reads,
            long snapshotMinimum,
            long snapshotMaximum,
            long unexpectedFailures
    ) {
        Map<V34LongRunCalibration.WorkloadKind, Long> kinds =
                new EnumMap<>(V34LongRunCalibration.WorkloadKind.class);
        for (V34LongRunCalibration.WorkloadKind kind
                : V34LongRunCalibration.WorkloadKind.values()) {
            kinds.put(kind, reads > 0 ? 1L : 0L);
        }
        return new V34LongRunCalibration.WindowResult(
                index,
                reads,
                reads > 0 ? 1L : 0L,
                reads > 0 ? 1L : 0L,
                reads > 0 ? 1L : 0L,
                0L,
                unexpectedFailures,
                reads > 0 ? 10L : 0L,
                reads > 0 ? 20L : 0L,
                reads > 0 ? 30L : 0L,
                reads > 0 ? 10L : 0L,
                reads > 0 ? 20L : 0L,
                reads > 0 ? 30L : 0L,
                0,
                32,
                1_000L,
                snapshotMinimum,
                snapshotMaximum,
                0L,
                0L,
                4L,
                kinds);
    }
}
