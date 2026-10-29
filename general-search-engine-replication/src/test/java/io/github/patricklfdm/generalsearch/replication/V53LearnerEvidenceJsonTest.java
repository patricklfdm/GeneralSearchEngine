package io.github.patricklfdm.generalsearch.replication;

import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V53LearnerEvidenceJsonTest {
    @TempDir Path temp;
    @Test void evidencePathsRemainDataAndProductionFieldNamesStayRestricted() {
        var value=Map.of("initial-typed",Map.of("members",Map.of(".",Map.of("directory",true),"backup/file",Map.of("key","inode-1"))),
                "cycle-4-before-transfer",Map.of("events",1L,"exchanges",2L));
        String expected="{\"cycle-4-before-transfer\":{\"events\":1,\"exchanges\":2},\"initial-typed\":{\"members\":{\".\":{\"directory\":true},\"backup/file\":{\"key\":\"inode-1\"}}}}";
        assertEquals(expected,new String(V53CurrentHeadNetworkTest.evidenceJson(value,4096),StandardCharsets.US_ASCII));
        assertThrows(ReplicationException.class,()->MembershipFormat.canonical(value,4096));
    }
    @Test void evidenceSerializationPreservesBoundAndEscaping() {
        var value=Map.of("a/\"b",List.of("\n\u03bb"));
        String expected="{\"a/\\\"b\":[\"\\n\\u03bb\"]}";
        byte[] bytes=V53CurrentHeadNetworkTest.evidenceJson(value,4096);
        assertEquals(expected,new String(bytes,StandardCharsets.US_ASCII));
        assertArrayEquals(bytes,V53CurrentHeadNetworkTest.evidenceJson(value,bytes.length));
        assertThrows(AssertionError.class,()->V53CurrentHeadNetworkTest.evidenceJson(value,bytes.length-1));
    }
    @Test void partialObservationsAreRetainedWithoutInventingSuccess()throws Exception {
        var stage=Map.<String,Object>of("cycle-4-before-transfer",Map.of("events",1L,"exchanges",0L));
        V53CurrentHeadNetworkTest.writeObservations(temp,List.of("LEARNER_STORE_BEFORE_RETURN"),List.of(),stage);
        assertEquals("[\"LEARNER_STORE_BEFORE_RETURN\"]",Files.readString(temp.resolve("current-head-events.json")));
        assertEquals("[]",Files.readString(temp.resolve("current-head-wire.json")));
        assertArrayEquals(V53CurrentHeadNetworkTest.evidenceJson(stage,16384),Files.readAllBytes(temp.resolve("current-head-stages.json")));
        assertFalse(Files.exists(temp.resolve("current-head-result.json")));
        Path legacy=Files.createDirectory(temp.resolve("legacy"));
        V53CurrentHeadNetworkTest.writeObservations(legacy,List.of(),List.of(),null);
        assertFalse(Files.exists(legacy.resolve("current-head-stages.json")));
    }
}
