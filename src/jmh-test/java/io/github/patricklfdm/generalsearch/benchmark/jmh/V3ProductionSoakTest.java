package io.github.patricklfdm.generalsearch.benchmark.jmh;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.junit.jupiter.api.Test;

class V3ProductionSoakTest {
    @Test
    void preservesDefaultSoakConfiguration() {
        var config = V3ProductionSoak.SoakConfig.parse(new String[0]);

        assertEquals(1, config.writerCount());
        assertEquals(V3ProductionSoak.UpdateMode.REVISION, config.updateMode());
        assertEquals(false, config.perQueryMetrics());
        assertEquals(true, config.indexCycles());
        assertEquals("none", config.investigationCell());
        assertEquals(V3ProductionSoak.StabilizationPurpose.NONE,
                config.stabilizationPurpose());
        assertEquals(0, config.stabilizationSeconds());
        assertEquals(null, config.jfrOutput());
    }

    @Test
    void parsesEveryInvestigationCellWithStrictValues() {
        var readOnly = config("0", "none");
        var stable = config("1", "stable");
        var revision = config("1", "revision");

        assertEquals("read-only", readOnly.investigationCell());
        assertEquals("stable-update", stable.investigationCell());
        assertEquals("revision-update", revision.investigationCell());
    }

    @Test
    void freezesProductionStabilizationPurposeMappings() {
        var screening = productionConfig("screening", "600");
        var confirmation = productionConfig("confirmation", "1800");
        var profile = productionConfig(
                "profile",
                "600",
                "--jfr-output=profile.jfr");

        assertEquals(300, screening.stabilizationSeconds());
        assertEquals(60, screening.stabilizationWindowSeconds());
        assertEquals(false, screening.allowReducedStabilizationTest());
        assertEquals(V3ProductionSoak.StabilizationPurpose.CONFIRMATION,
                confirmation.stabilizationPurpose());
        assertEquals("profile.jfr", profile.jfrOutput().toString());
        assertThrows(IllegalArgumentException.class, () ->
                productionConfig("profile", "600"));
        assertThrows(IllegalArgumentException.class, () ->
                productionConfig("screening", "601"));
    }

    @Test
    void rejectsUnknownBooleanAndWriterModeConflicts() {
        assertThrows(IllegalArgumentException.class, () ->
                V3ProductionSoak.SoakConfig.parse(new String[]{
                        "--per-query-metrics=True"
                }));
        assertThrows(IllegalArgumentException.class, () -> reducedConfig(
                "--allow-reduced-stabilization-test=False"));
        assertThrows(IllegalArgumentException.class, () -> reducedConfig(
                "--stabilization-seconds=9"));
        assertThrows(IllegalArgumentException.class, () ->
                V3ProductionSoak.SoakConfig.parse(new String[]{
                        "--stabilization-purpose=screening",
                        "--stabilization-seconds=300",
                        "--stabilization-window-seconds=60",
                        "--seconds=600",
                        "--readers=16",
                        "--writers=1",
                        "--update-mode=stable",
                        "--index-cycles=false",
                        "--per-query-metrics=true",
                        "--jfr-output=unexpected.jfr"
                }));
        assertThrows(IllegalArgumentException.class, () ->
                V3ProductionSoak.SoakConfig.parse(new String[]{
                        "--writers=0", "--update-mode=revision"
                }));
        assertThrows(IllegalArgumentException.class, () ->
                V3ProductionSoak.SoakConfig.parse(new String[]{
                        "--writers=1", "--update-mode=none"
                }));
        assertThrows(IllegalArgumentException.class, () ->
                V3ProductionSoak.SoakConfig.parse(new String[]{
                        "--writers=1", "--update-mode=stable",
                        "--per-query-metrics=true", "--index-cycles=true"
                }));
    }

    @Test
    void queryCountersKeepKindsIndependent() {
        var counters = new V3ProductionSoak.QueryCounters();
        counters.record(V3ProductionSoak.QueryKind.TEXT, 11L);
        counters.record(V3ProductionSoak.QueryKind.TEXT, 13L);
        counters.record(V3ProductionSoak.QueryKind.FUZZY, 17L);

        var snapshot = counters.snapshot();
        assertEquals(2L, snapshot.operations(V3ProductionSoak.QueryKind.TEXT));
        assertEquals(24L,
                snapshot.latencyNanoseconds(V3ProductionSoak.QueryKind.TEXT));
        assertEquals(1L, snapshot.operations(V3ProductionSoak.QueryKind.FUZZY));
        assertEquals(0L, snapshot.operations(V3ProductionSoak.QueryKind.BOOL));
        assertThrows(IllegalArgumentException.class, () ->
                counters.record(V3ProductionSoak.QueryKind.PHRASE, -1L));
    }

    @Test
    void latencyReservoirSamplingIsBoundedAndDeterministic() {
        var first = new V3ProductionSoak.LatencyReservoir(8, 41L);
        var second = new V3ProductionSoak.LatencyReservoir(8, 41L);
        for (long latency = 1; latency <= 100; latency++) {
            first.record(latency);
            second.record(latency);
        }

        assertEquals(8, first.size());
        assertArrayEquals(first.samples(), second.samples());
        assertEquals(100L, first.max());
    }

    @Test
    void canonicalDigestSeparatesStableAndRevisionUpdates() {
        try (var fixture = V3ProductionBenchmarkSupport.createFixture(
                8,
                "zipf-en-medium-4")) {
            String initial = V3ProductionSoak.corpusDigest(fixture, 8);
            long initialSnapshot = fixture.engine().metrics().snapshotVersion();
            fixture.engine().update(V3ProductionBenchmarkSupport.replacement(
                    3L,
                    0,
                    fixture.profile())).join();
            String stable = V3ProductionSoak.corpusDigest(fixture, 8);
            long stableSnapshot = fixture.engine().metrics().snapshotVersion();
            fixture.engine().update(V3ProductionBenchmarkSupport.replacement(
                    3L,
                    1,
                    fixture.profile())).join();
            String revision = V3ProductionSoak.corpusDigest(fixture, 8);
            long revisionSnapshot = fixture.engine().metrics().snapshotVersion();

            assertEquals(initial, stable);
            assertNotEquals(initial, revision);
            assertEquals(64, revision.length());
            assertEquals(initialSnapshot + 1, stableSnapshot);
            assertEquals(stableSnapshot + 1, revisionSnapshot);
        }
    }

    @Test
    void reducedReadinessUsesFiveWindowsAndLastThreeBands() {
        var config = reducedConfig();
        List<V3ProductionSoak.StabilizationSample> samples = stableSamples();

        var decision = V3ProductionSoak.evaluateReadiness(
                config,
                samples,
                41L,
                41L,
                "same",
                "same",
                100,
                0L,
                true);

        assertEquals(true, decision.ready());
        assertArrayEquals(new int[]{2, 2, 2, 2, 3},
                decision.windowSampleCounts());
    }

    @Test
    void changedIdentityCannotStartMeasurement() {
        var decision = V3ProductionSoak.evaluateReadiness(
                reducedConfig(),
                stableSamples(),
                41L,
                42L,
                "loaded",
                "changed",
                100,
                0L,
                true);

        assertEquals(false, decision.ready());
        assertEquals(false, decision.snapshotUnchanged());
        assertEquals(false, decision.corpusUnchanged());
        assertEquals(V3ProductionSoak.SoakPhase.NOT_READY,
                V3ProductionSoak.nextPhaseAfterReadiness(decision.ready()));
        assertEquals(V3ProductionSoak.SoakPhase.MEASURE_SELECTED_CELL,
                V3ProductionSoak.nextPhaseAfterReadiness(true));
    }

    private static V3ProductionSoak.SoakConfig config(
            String writers,
            String updateMode
    ) {
        return V3ProductionSoak.SoakConfig.parse(new String[]{
                "--writers=" + writers,
                "--update-mode=" + updateMode,
                "--index-cycles=false",
                "--per-query-metrics=true"
        });
    }

    private static V3ProductionSoak.SoakConfig reducedConfig(
            String... overrides
    ) {
        List<String> arguments = new ArrayList<>(List.of(
                "--documents=100",
                "--readers=4",
                "--writers=1",
                "--seconds=12",
                "--sample-seconds=1",
                "--update-mode=stable",
                "--index-cycles=false",
                "--per-query-metrics=true",
                "--stabilization-purpose=reduced-test",
                "--stabilization-seconds=10",
                "--stabilization-window-seconds=2",
                "--allow-reduced-stabilization-test=true"));
        for (String override : overrides) {
            String name = override.substring(0, override.indexOf('=') + 1);
            arguments.removeIf(value -> value.startsWith(name));
            arguments.add(override);
        }
        return V3ProductionSoak.SoakConfig.parse(arguments.toArray(String[]::new));
    }

    private static V3ProductionSoak.SoakConfig productionConfig(
            String purpose,
            String seconds,
            String... extra
    ) {
        List<String> arguments = new ArrayList<>(List.of(
                "--documents=100",
                "--readers=16",
                "--writers=1",
                "--seconds=" + seconds,
                "--sample-seconds=1",
                "--update-mode=stable",
                "--index-cycles=false",
                "--per-query-metrics=true",
                "--stabilization-purpose=" + purpose,
                "--stabilization-seconds=300",
                "--stabilization-window-seconds=60"));
        arguments.addAll(List.of(extra));
        return V3ProductionSoak.SoakConfig.parse(arguments.toArray(String[]::new));
    }

    private static List<V3ProductionSoak.StabilizationSample> stableSamples() {
        List<V3ProductionSoak.StabilizationSample> samples = new ArrayList<>();
        for (int second = 0; second <= 10; second++) {
            long[] operations = new long[4];
            long[] latency = new long[4];
            for (int query = 0; query < 4; query++) {
                operations[query] = second * 100L;
                latency[query] = operations[query] * (1_000L + query * 100L);
            }
            samples.add(new V3ProductionSoak.StabilizationSample(
                    Instant.EPOCH.plusSeconds(second),
                    second,
                    1_000_000L,
                    2_000_000L,
                    4_000_000L,
                    second * 400L,
                    Arrays.stream(latency).sum(),
                    new V3ProductionSoak.QueryCounterSnapshot(operations, latency),
                    0L,
                    41L,
                    100,
                    second,
                    second));
        }
        return samples;
    }
}
