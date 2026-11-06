package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Real local application/publication; historical provisioning is conditional. */
class V53CompletionPrefixCaptureTest {
    @TempDir Path temp;
    @Test void dataIntentAndFinalRetainOriginalApplicationAndPublicationPrefixes()throws Exception {
        for(int at:List.of(0,5,6)) {
            var f=new V53JournalPublicationTest.Fixture(temp.resolve("at-"+at),at,false);
            Path raw=Files.createDirectories(Path.of("target/v53-completion-prefix-component/run-"+UUID.randomUUID()));
            System.out.println("v53CompletionPrefixComponentEvidence="+raw.toAbsolutePath());
            var capture=new V53RemoveRetirementCapture(raw,raw.resolve("captures"),V53RemoveRetirementCapture.Mode.COMPLETION);
            var events=new ArrayList<Map<String,Object>>();var resources=f.resources();Path replica=f.node(1);
            V53JournalApplicationTest.copy(replica,raw.resolve("before"));
            try(var store=f.open(1,resources,point->{
                int index=events.size();events.add(Map.of("node","node-1","event",point));capture.at("node-1",replica,point,index);
            })) {
                var applied=f.application.apply(store);f.applied.put(1,applied);
                f.acknowledgements.addFirst(applied.endorsement().acknowledgement());f.checkpoints.add(applied.endorsement().owned());
                f.observations.addAll(f.checkpoints);
                var parentAcks=new ArrayList<Decoded>();var parentOwned=new HashSet<Owned>();Decoded parentStatement=null;
                for(var result:f.applied.values())if(result.endorsement().parent().isPresent()) {
                    var parent=result.endorsement().parent().orElseThrow();parentStatement=parent.statement();
                    parentAcks.add(parent.acknowledgement());parentOwned.add(parent.owned());
                }
                f.bridges.clear();if(parentStatement!=null) {
                    f.bridges.add(new MembershipSelection.Bridge(parentStatement,parentAcks,parentOwned));f.observations.addAll(parentOwned);
                }
                V53JournalApplicationTest.copy(replica,raw.resolve("applied"));
                f.publish(store,1);new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
            }
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(replica,raw.resolve("published"));
            byte[] encoded=canonical(events,1024*1024);Files.write(raw.resolve("events.json"),encoded);
            String root=f.application.f.f.f.root().manifestDigest();capture.finishProcess(root,2,"CLOSED",encoded);
            Files.write(raw.resolve("result.json"),canonical(Map.of("schema","gse-v53-completion-prefix-component-v1","at",at,
                    "pid",ProcessHandle.current().pid(),"root",root,"protocolAuthority","conditional-initial-history",
                    "nativeCarriedProcess",false),4096));
            assertTrue(number(object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096)).get("captures"))>80);
        }
    }
    @Test void installationOutsidePublicationIsNotRelabelledAndPartialEndCannotClose()throws Exception {
        Path replica=Files.createDirectory(temp.resolve("replica"));Files.write(replica.resolve("empty"),new byte[0]);
        var capture=new V53RemoveRetirementCapture(replica,temp.resolve("captures"),V53RemoveRetirementCapture.Mode.COMPLETION);
        capture.at("node-1",replica,"INSTALL_RESERVED",0);capture.at("node-1",replica,"CURRENT_VALIDATED",1);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"COVERED_END_VALIDATED",2));
        capture.at("node-1",replica,"APPLY_VALIDATED",3);capture.at("node-1",replica,"APPLY_ACK_DIRECTORY_FORCED",4);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"PUBLICATION_VALIDATED",5));
        assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
        assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]));
    }
    @Test void completedOwnersAndEmptyPreApplicationCrashKeepTheirOriginalTerminals()throws Exception {
        Path replica=Files.createDirectory(temp.resolve("replica"));Files.write(replica.resolve("empty"),new byte[0]);
        var empty=new V53RemoveRetirementCapture(replica,temp.resolve("empty-captures"),V53RemoveRetirementCapture.Mode.COMPLETION);
        empty.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]);
        var capture=new V53RemoveRetirementCapture(replica,temp.resolve("captures"),V53RemoveRetirementCapture.Mode.COMPLETION);
        capture.at("node-1",replica,"APPLY_VALIDATED",0);capture.at("node-2",replica,"APPLY_VALIDATED",1);
        capture.at("node-1",replica,"APPLY_BEFORE_RETURN",2);capture.at("node-2",replica,"APPLY_BEFORE_RETURN",3);
        capture.at("node-1",replica,"PUBLICATION_VALIDATED",4);capture.at("node-1",replica,"INSTALL_RESERVED",5);
        capture.at("node-1",replica,"PUBLICATION_BEFORE_RETURN",6);
        capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]);
        assertEquals(7L,object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096)).get("captures"));
    }
}
