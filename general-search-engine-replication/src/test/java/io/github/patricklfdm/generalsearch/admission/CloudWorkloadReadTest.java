package io.github.patricklfdm.generalsearch.admission;

import static org.junit.jupiter.api.Assertions.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;

class CloudWorkloadReadTest {
    @SuppressWarnings("unchecked")
    private static List<Map<String,Object>> attempts(Map<String,Object> row) {
        return (List<Map<String,Object>>)row.get("readAttempts");
    }

    @Test void publicationDuringQueryRetainsBothAttemptsAndTheFreshAnswer() {
        var sequence=new AtomicLong(256); var calls=new AtomicInteger();
        var row=new TreeMap<String,Object>();
        var answer=CloudWorkload.sampleLocalQuery(sequence::get, () -> {
            if (calls.incrementAndGet()==1) {
                sequence.incrementAndGet();
                return List.of(1,2); // Answer from the old snapshot; concurrent publication changes membership.
            }
            return List.of(2);
        }, row);
        assertEquals(List.of(2),answer); assertEquals(2,calls.get());
        assertEquals(257L,row.get("beforeSequence")); assertEquals(257L,row.get("afterSequence"));
        var attempts=attempts(row); assertEquals(2,attempts.size());
        assertEquals(256L,attempts.getFirst().get("beforeSequence"));
        assertEquals(257L,attempts.getFirst().get("afterSequence"));
        assertEquals(PerformanceWorkload.digest(List.of(1,2)),attempts.getFirst().get("answerDigest"));
        assertEquals(PerformanceWorkload.digest(answer),attempts.getLast().get("answerDigest"));
        assertTrue((long)attempts.getFirst().get("endNanos")<=(long)attempts.getLast().get("startNanos"));
    }

    @Test void stableQueryIsExecutedOnceAndItsAnswerIsNotReplacedByAnOracle() {
        var calls=new AtomicInteger(); var row=new TreeMap<String,Object>();
        var answer=CloudWorkload.sampleLocalQuery(() -> 256, () -> {
            calls.incrementAndGet(); return List.of(999);
        }, row);
        assertEquals(List.of(999),answer); assertEquals(1,calls.get());
        assertEquals(PerformanceWorkload.digest(answer),attempts(row).getFirst().get("answerDigest"));
    }

    @Test void continuousPublicationExhaustsTheBoundWithoutInventingAStableCut() {
        var sequence=new AtomicLong(256); var row=new TreeMap<String,Object>();
        assertThrows(IllegalArgumentException.class, () -> CloudWorkload.sampleLocalQuery(sequence::get,
                () -> List.of(sequence.incrementAndGet()),row));
        assertEquals(260,sequence.get()); assertEquals(4,attempts(row).size());
        assertFalse(row.containsKey("afterSequence"));
    }

    @Test void queryFailureAndSequenceRegressionAreNotRetried() {
        var calls=new AtomicInteger(); var failure=new IllegalStateException("query failed");
        assertSame(failure,assertThrows(IllegalStateException.class, () ->
                CloudWorkload.sampleLocalQuery(() -> 256, () -> { calls.incrementAndGet(); throw failure; },new HashMap<>())));
        assertEquals(1,calls.get());
        var sequence=new AtomicLong(256); var row=new HashMap<String,Object>();
        assertThrows(IllegalArgumentException.class, () -> CloudWorkload.sampleLocalQuery(sequence::get,
                () -> sequence.decrementAndGet(),row));
        assertEquals(1,attempts(row).size());
    }
}
