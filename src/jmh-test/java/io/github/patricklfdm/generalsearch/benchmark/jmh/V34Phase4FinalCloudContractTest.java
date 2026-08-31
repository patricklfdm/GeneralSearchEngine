package io.github.patricklfdm.generalsearch.benchmark.jmh;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class V34Phase4FinalCloudContractTest {
    @Test
    void finalCloudKindAcceptsOnlyFrozenThirtyMinuteOrTwoHourWindows() {
        var canonical = V34LongRunCalibration.Config.parse(new String[]{
                "--run-kind=final-v34-cloud",
                "--seconds=1800"
        });
        var extended = V34LongRunCalibration.Config.parse(new String[]{
                "--run-kind=final-v34-cloud",
                "--seconds=7200"
        });

        assertEquals("final-v34-cloud", canonical.runKind());
        assertEquals(1_800, canonical.seconds());
        assertEquals(7_200, extended.seconds());
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--run-kind=final-v34-cloud",
                        "--seconds=21600"
                }));
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--run-kind=final-v34-cloud",
                        "--seconds=43200"
                }));
    }

    @Test
    void localCalibrationCannotSilentlyBecomeTwoHourCloudEvidence() {
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--seconds=7200"
                }));
        assertThrows(IllegalArgumentException.class, () ->
                V34LongRunCalibration.Config.parse(new String[]{
                        "--run-kind=unknown",
                        "--seconds=1800"
                }));
    }
}
