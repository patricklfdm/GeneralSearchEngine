package io.github.patricklfdm.generalsearch.benchmark.jmh;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

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
    void rejectsUnknownBooleanAndWriterModeConflicts() {
        assertThrows(IllegalArgumentException.class, () ->
                V3ProductionSoak.SoakConfig.parse(new String[]{
                        "--per-query-metrics=True"
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
}
