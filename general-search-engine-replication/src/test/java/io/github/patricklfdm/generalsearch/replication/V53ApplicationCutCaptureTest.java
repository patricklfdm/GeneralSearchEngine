package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ApplicationCutCaptureTest {
    @TempDir Path temp;
    private V53RemoveRetirementCapture capture(String name)throws Exception {
        Path replica=Files.createDirectory(temp.resolve(name));Files.write(replica.resolve("empty"),new byte[0]);
        return new V53RemoveRetirementCapture(replica,temp.resolve(name+"-capture"),V53RemoveRetirementCapture.Mode.COMPLETION);
    }
    private List<Map<String,Object>> events() {
        return List.of(Map.of("node","node-1","event","APPLY_VALIDATED"),Map.of("node","node-1","event","APPLY_ACK_DIRECTORY_FORCED"));
    }
    private void record(V53RemoveRetirementCapture capture,List<Map<String,Object>> events)throws Exception {
        for(int i=0;i<events.size();i++)capture.at((String)events.get(i).get("node"),capture.raw,(String)events.get(i).get("event"),i);
    }
    @Test void explicitInterruptedTerminalCannotBeRelabelledAsNormalCompletion()throws Exception {
        var c=capture("exact");var rows=events();record(c,rows);
        assertThrows(IllegalArgumentException.class,()->c.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",V53EvidenceArray.encode(rows,4096)));
        c.finishApplicationCut(hash(new byte[0]),1,"CUT_PREFIX",rows);
        var header=object(parse(Files.readAllBytes(c.root.resolve("collection.json")),4096));
        assertEquals(V53RemoveRetirementCapture.APPLICATION_CUT_SCHEMA,header.get("schema"));
        assertEquals(Map.of("node","node-1","point","APPLY_ACK_DIRECTORY_FORCED","eventIndex",1L),header.get("interrupted"));
        assertEquals(hash(V53EvidenceArray.encode(rows,4096)),header.get("eventsSha256"));
        assertThrows(IllegalArgumentException.class,()->c.finishApplicationCut(hash(new byte[0]),1,"CUT_PREFIX",rows));
    }
    @Test void wrongTerminalLifetimeAndLaterEventsCannotSealPrefix()throws Exception {
        var c=capture("lifetime");var rows=events();record(c,rows);
        assertThrows(IllegalArgumentException.class,()->c.finishApplicationCut(hash(new byte[0]),2,"CUT_PREFIX",rows));
        assertThrows(IllegalArgumentException.class,()->c.finishApplicationCut(hash(new byte[0]),1,"CLOSED",rows));
        for(String event:List.of("APPLY_BEFORE_RETURN","WIRE_RESPONSE")) {
            var changed=new ArrayList<>(rows);changed.add(Map.of("node","node-1","event",event));
            assertThrows(IllegalArgumentException.class,()->c.finishApplicationCut(hash(new byte[0]),1,"CUT_PREFIX",changed));
        }
        assertFalse(Files.exists(c.root.resolve("collection.json")));
    }
    @Test void wrongOwnerMissingAckOtherOpenOwnerAndNormalReturnRefuse()throws Exception {
        var variants=List.of(
                List.<Map<String,Object>>of(Map.of("node","node-2","event","APPLY_VALIDATED"),Map.of("node","node-2","event","APPLY_ACK_DIRECTORY_FORCED")),
                events().subList(0,1),
                List.<Map<String,Object>>of(Map.of("node","node-2","event","APPLY_VALIDATED"),events().getFirst(),events().getLast()),
                List.<Map<String,Object>>of(events().getFirst(),events().getLast(),Map.of("node","node-1","event","APPLY_BEFORE_RETURN")));
        for(int i=0;i<variants.size();i++) {
            var c=capture("variant-"+i);var rows=variants.get(i);record(c,rows);
            assertThrows(IllegalArgumentException.class,()->c.finishApplicationCut(hash(new byte[0]),1,"CUT_PREFIX",rows));
            assertFalse(Files.exists(c.root.resolve("collection.json")));
        }
    }
    @Test void anotherCollectorModeCannotClaimApplicationInterruption()throws Exception {
        var c=new V53RemoveRetirementCapture(temp,temp.resolve("vote"),V53RemoveRetirementCapture.Mode.VOTE);
        assertThrows(IllegalArgumentException.class,()->c.finishApplicationCut(hash(new byte[0]),1,"CUT_PREFIX",events()));
    }
}
