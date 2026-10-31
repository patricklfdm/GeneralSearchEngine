package io.github.patricklfdm.generalsearch.replication;

import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53EvidenceArrayTest {
    @Test void largerProfileTraceExceedsLegacyEnvelopeWithoutChangingAnyRow() {
        var row=Map.of("bytes","x".repeat(600_000));var rows=Collections.nCopies(30,row);
        assertThrows(IllegalArgumentException.class,()->V53EvidenceArray.encode(rows,16*1024*1024));
        byte[] actual=V53EvidenceArray.encode(rows,V53EvidenceArray.WIRE_BYTES);
        assertTrue(actual.length>16*1024*1024);assertTrue(actual.length<V53EvidenceArray.WIRE_BYTES);
        String one=new String(MembershipFormat.canonical(row,1024*1024),StandardCharsets.US_ASCII);
        assertEquals("["+String.join(",",Collections.nCopies(30,one))+"]",new String(actual,StandardCharsets.US_ASCII));
    }
    @Test void aggregateHistoryRowLimitIsIndependentOfPerMessageTokens() {
        var row=Map.of("event","force");
        assertNotNull(V53EvidenceArray.encode(Collections.nCopies(V53EvidenceArray.HISTORY_ROWS,row),V53EvidenceArray.EVENT_BYTES));
        assertEquals("evidence array row capacity",assertThrows(IllegalArgumentException.class,()->
            V53EvidenceArray.encode(Collections.nCopies(V53EvidenceArray.HISTORY_ROWS+1,row),V53EvidenceArray.EVENT_BYTES)).getMessage());
    }
    @Test void completeTraceExceedsOneMessageTokensWithoutLosingAnyOrderedRow() {
        var rows=new ArrayList<Object>();var expected=new StringJoiner(",","[","]");
        for(int i=0;i<20_000;i++) {
            rows.add(Map.of("node","node-1","event","event-"+i));
            expected.add("{\"event\":\"event-"+i+"\",\"node\":\"node-1\"}");
        }
        assertEquals("JSON token budget",assertThrows(IllegalArgumentException.class,
                ()->MembershipFormat.canonical(rows,8*1024*1024)).getMessage());
        assertEquals(expected.toString(),new String(V53EvidenceArray.encode(rows,8*1024*1024),StandardCharsets.US_ASCII));
    }
    @Test void aggregateByteLimitStillIncludesDelimitersAndEmptyArray() {
        var rows=List.of(Map.of("event","one"),Map.of("event","two"));
        var bytes=V53EvidenceArray.encode(rows,1024);
        assertArrayEquals(bytes,V53EvidenceArray.encode(rows,bytes.length));
        assertThrows(IllegalArgumentException.class,()->V53EvidenceArray.encode(rows,bytes.length-1));
        assertArrayEquals(new byte[]{'[',']'},V53EvidenceArray.encode(List.of(),2));
        assertThrows(IllegalArgumentException.class,()->V53EvidenceArray.encode(List.of(),1));
    }
    @Test void individualRecordsKeepTheOriginalTokenDepthAndFieldChecks() {
        var oversized=Collections.nCopies(70_000,"event");
        assertThrows(IllegalArgumentException.class,()->V53EvidenceArray.encode(List.of(oversized),1024*1024));
        Object nested="leaf";for(int i=0;i<17;i++)nested=List.of(nested);var row=nested;
        assertThrows(ReplicationException.class,()->V53EvidenceArray.encode(List.of(row),1024));
        assertThrows(ReplicationException.class,()->V53EvidenceArray.encode(List.of(Map.of("bad-key",1)),1024));
    }
    @Test void existingSmallHistoriesKeepIdenticalCanonicalBytes() {
        var rows=List.of(Map.of("node","node-1","event","\n\u03bb\""),Map.of("calls",List.of(1L,2L)));
        assertArrayEquals(MembershipFormat.canonical(rows,4096),V53EvidenceArray.encode(rows,4096));
    }
}
