package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static org.junit.jupiter.api.Assertions.*;

/** One continuation producer; the short replay smoke is explicitly not a capacity test. */
final class V53CapacityCompletionFixture {
    static void run(Path owners,Path output,V53EnvelopeHistoryFixture history,MembershipCapsule sealed,
                    MembershipPublicationCapacity.Budget reservation,int change,V53ApplicationReplayTest application)throws Exception {
        assertTrue(change==1 || change==231);boolean boundary=change==231;
        var f=new V53EnvelopeOwnerFixture(owners,history,sealed);f.trace(output);
        try {
            var operation=object(list(sealed.context.catalog.get("results")).getFirst());var descriptor=new TreeMap<String,Object>();
            for(String k:List.of("request","prepared","receipt"))descriptor.put(k,operation.get(k));
            var joint=f.publish("INTENT",command("INTENT",Map.of("sealed",descriptor)),application);
            V53PublicationCapacityTest.withinReservation(joint,reservation);assertNotNull(joint.context.view.get("operation"));
            f.campaign();
            var completed=f.publish("FINAL",command("FINAL",Map.of("binding",operation.get("binding"))),application);
            V53PublicationCapacityTest.withinReservation(completed,reservation);assertNull(completed.context.view.get("operation"));
            f.campaign();
            V53PublicationCapacityTest.withinReservation(f.publish("BARRIER",new byte[0],application),reservation);
            V53PublicationCapacityTest.withinReservation(f.publish("RETIRE",command("RETIRE",Map.of("through",(long)change)),application),reservation);
            assertTrue(list(f.current.context.catalog.get("results")).isEmpty());
            assertEquals(!boundary,MembershipPublicationCapacity.publication(f.current,null,"RESERVE",8192,0).fits());
            if(boundary) {
                var target=new ArrayList<Map<String,Object>>();for(int n=1;n<=4;n++)target.add(V53ContextFixture.member(n));target.add(V53ContextFixture.member(6+change));
                target.sort(Comparator.comparing(v->(String)v.get("node")));
                byte[] refused=command("RESERVE",Map.of("request",Map.of("root",f.root.manifestDigest(),"expected",f.current.context.authority(),
                        "number",(long)change+1,"kind","REPLACE","target",target)));
                Files.write(output.resolve("refused-entry.gsr"),f.entry("RESERVE",refused).bytes());Files.write(output.resolve("refused-payload.bin"),refused);
                f.evidence=output.resolve("refusal");f.refuse("RESERVE",refused);
            }
            byte[] payload;try(var encoder=application.encoder()) {
                payload=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(21,"admitted-completion"))));
            }
            var after=f.publish("DATA",payload,application);
            assertEquals(number(sealed.context.cut.get("index"))+5,number(after.context.cut.get("index")));
            assertEquals(42L,after.context.catalog.get("applicationSequence"));assertEquals(completed.context.view,after.context.view);
            for(int n:f.voters)try(var owner=f.open(n)) {
                var copy=owner.floorCopyCurrent();assertEquals(after.context.cut,copy.capsule.context.cut);
                var loaded=application.read(copy.fileBytes(copy.capsule.terminal().application()+".image"),"completion-data-"+n);
                assertTrue(loaded.documents().contains(new io.github.patricklfdm.generalsearch.admission.OfflineApplication.Doc(21,"admitted-completion")));
            }
        } finally {f.finishTrace();}
        var receipt=new TreeMap<String,Object>();receipt.put("schema","gse-v53-capacity-completion-v2");receipt.put("status","PASS");
        receipt.put("profile",boundary?"capacity-231":"replay-smoke-1");receipt.put("completedOperation",change);
        receipt.put("nextOperationRefused",boundary?change+1:null);receipt.put("applicationSequence",42);receipt.put("nodes",3);
        receipt.put("conditionalPrefix",true);receipt.put("freshProcesses",false);receipt.put("nativeNetwork",false);receipt.put("phase3Complete",false);
        Files.write(output.resolve("receipt.json"),canonical(receipt,65536));
        System.out.println("v53CapacityCompletionEvidence="+output.toAbsolutePath());
    }
}
