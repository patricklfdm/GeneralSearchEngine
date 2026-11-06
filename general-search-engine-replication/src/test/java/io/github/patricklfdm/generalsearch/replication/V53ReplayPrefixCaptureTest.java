package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real typed control replay; the provisioned protocol history is conditional. */
class V53ReplayPrefixCaptureTest {
    @TempDir Path temp;
    @Test void intentAndFinalCaptureExactScratchAndContinuousCompletionReservations()throws Exception {
        for(int at:List.of(5,6)) {
            var f=new V53JournalApplicationTest();f.setup(temp.resolve("at-"+at),3,at);
            Path replica=f.f.f.node(temp.resolve("at-"+at),1);
            Path raw=Files.createDirectories(Path.of("target/v53-replay-prefix-component/run-"+UUID.randomUUID()));
            System.out.println("v53ReplayPrefixComponentEvidence="+raw.toAbsolutePath());
            var capture=new V53RemoveRetirementCapture(raw,raw.resolve("captures"),V53RemoveRetirementCapture.Mode.REPLAY);
            var events=new ArrayList<Map<String,Object>>();var boundaries=new ArrayList<Map<String,Object>>();
            var resources=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                    MembershipResources.QUEUE_LIMIT,32768);
            V53JournalApplicationTest.copy(replica,raw.resolve("before"));
            try(var store=f.open(temp.resolve("at-"+at),1,resources,point->{
                int index=events.size();events.add(Map.of("node","node-1","event",point));
                var observed=resources.observationCheckpoint();assertTrue(observed.complete());
                boundaries.add(Map.of("eventIndex",index,"node","node-1","sequence",observed.sequence(),
                        "usage",V53ResourceTraceFiles.usage(observed.usage())));
                capture.at("node-1",replica,point,index);
            })) {
                f.apply(store);new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"));
            }
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(replica,raw.resolve("applied"));
            byte[] encoded=canonical(events,1024*1024);Files.write(raw.resolve("events.json"),encoded);
            Files.write(raw.resolve("boundaries.json"),V53EvidenceArray.encode(boundaries,1024*1024));
            V53ResourceTraceFiles.write(raw.resolve("resources.json"),resources.observations());
            String root=f.f.f.f.root().manifestDigest();capture.finishProcess(root,2,"CLOSED",encoded);
            Files.write(raw.resolve("result.json"),canonical(Map.of("schema","gse-v53-replay-prefix-component-v1","at",at,
                    "pid",ProcessHandle.current().pid(),"root",root,"protocolAuthority","conditional-initial-history",
                    "nativeCarriedProcess",false),4096));
            assertEquals(23L,object(parse(Files.readAllBytes(capture.root.resolve("collection.json")),4096)).get("captures"));
        }
    }
    @Test void incompleteScratchCannotBorrowVoteCrashExceptionOrClose()throws Exception {
        Path replica=Files.createDirectory(temp.resolve("replica"));Files.write(replica.resolve("empty"),new byte[0]);
        var capture=new V53RemoveRetirementCapture(replica,temp.resolve("captures"),V53RemoveRetirementCapture.Mode.REPLAY);
        capture.at("node-1",replica,"APPLY_VALIDATED",0);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"REPLAY_CLAIM_FORCED",1));
        capture.at("node-1",replica,"REPLAY_RESERVED",2);
        assertThrows(IllegalArgumentException.class,()->capture.at("node-1",replica,"REPLAY_RESERVED",3));
        assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]));
        assertThrows(IllegalArgumentException.class,()->capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]));
    }
    @Test void distinctOwnersCompleteAndEmptyPreApplicationCrashRetainsNoFiles()throws Exception {
        Path replica=Files.createDirectory(temp.resolve("replica"));Files.write(replica.resolve("empty"),new byte[0]);
        var empty=new V53RemoveRetirementCapture(replica,temp.resolve("empty-captures"),V53RemoveRetirementCapture.Mode.REPLAY);
        empty.finishProcess(hash(new byte[0]),1,"CUT_PREFIX",new byte[0]);
        var capture=new V53RemoveRetirementCapture(replica,temp.resolve("captures"),V53RemoveRetirementCapture.Mode.REPLAY);
        capture.at("node-1",replica,"REPLAY_RESERVED",0);capture.at("node-2",replica,"REPLAY_RESERVED",1);
        capture.at("node-1",replica,"REPLAY_BEFORE_RETURN",2);capture.at("node-2",replica,"REPLAY_BEFORE_RETURN",3);
        capture.finishProcess(hash(new byte[0]),2,"CLOSED",new byte[0]);
    }
}
