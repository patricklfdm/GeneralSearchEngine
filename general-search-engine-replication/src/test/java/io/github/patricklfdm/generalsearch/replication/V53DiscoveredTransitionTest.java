package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** One original five-to-four history. Preparation uses actual local forces;
 * recovery and service use the real private TCP owner, with no injected hint,
 * copied disk, supplied historical observations or restored READY state. */
class V53DiscoveredTransitionTest {
    @TempDir Path temp;

    void prepare(V53BootstrapPublicationTest.Fixture f)throws Exception {
        try {
            var all=f.request.targets();var stale=all.get(3);var online=all.stream().filter(t->!t.equals(stale)).toList();
            var newView=List.copyOf(all.subList(0,4));var governing=List.copyOf(all.subList(0,3));
            var walk=new V53AdmittedCrossViewTest.Walk(f);var original=V53ReplayFilesTest.files(stale.replicaDirectory());
            walk.afterPublication=(kind,targets)->{
                if(kind.equals("INTENT") || kind.equals("FINAL"))for(var target:targets)
                    try(var owner=f.open(target,"configuration-retention")){owner.reconcilePeerRetention(List.of());}
            };
            walk.publish("BARRIER",null,online);
            var context=walk.current();
            var request=Map.of("root",context.root,"expected",context.authority(),"number",1L,"kind","REMOVE",
                    "target",newView.stream().map(t->MembershipBootstrapSeed.identity(t.identity())).toList());
            walk.publish("RESERVE",Map.of("request",request),online);
            walk.publish("PREPARE",Map.of("number",1L,"revision",1L),online);
            walk.publish("READY",V53ContextFixture.map("number",1L,"receipt",null),online);
            walk.publish("SEAL",Map.of("number",1L),online);
            var operation=walk.operation();
            walk.publish("INTENT",Map.of("sealed",V53ContextFixture.map("request",operation.get("request"),
                    "prepared",operation.get("prepared"),"receipt",operation.get("receipt"))),online);
            walk.campaign(governing);
            walk.publish("FINAL",Map.of("binding",operation.get("binding")),governing);
            assertEquals(original,V53ReplayFilesTest.files(stale.replicaDirectory()),"offline original must not be repaired by setup");
            try(var owner=f.open(stale,"stale-survivor-original")){assertEquals(0L,owner.activationContext().cut.get("index"));}
            try(var owner=f.open(all.getLast(),"removed-original")){assertEquals(6L,owner.activationContext().cut.get("index"));}
            assertEquals(7L,walk.current().cut.get("index"));f.snapshot("heterogeneous-originals");
        }finally {
            V53NativeApplicationTest.save(f);
            Files.write(f.raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        }
    }
    MembershipRoundDriver<?,?> round(V53NativeDispatchTest.Network n,int index)throws Exception {
        String node=n.owners.get(index).activationIdentity().nodeId().value();
        return new MembershipRoundDriver<>(n.owners.get(index),n.endpoints.get(index),n.resources.get(index),n.bounds,n.transports.get(index),
                temp.resolve("discovered-"+node),System::nanoTime,V53NativeDispatchTest.BUDGET,2,
                builder().configuration(),n.f.request.targets().get(index).materialization(),(event,record)->{
                    n.events.add(Map.of("node",node,"event","ROUND_"+event,"record",record.digest(),"bytes",Base64.getEncoder().encodeToString(record.bytes())));
                    if(event.equals("ADOPTED") || event.equals("INSTALLED"))try{n.f.snapshot(node+"-"+event.toLowerCase(Locale.ROOT));}
                    catch(Exception error){throw new IOException(error);}
                },(event,record,voters)->{
                    n.events.add(Map.of("node",node,"event","SLOT_"+event,"record",record.digest(),"voters",voters.stream().sorted().toList()));
                });
    }
    @Test void obsoleteSurvivorRecoversServiceWhileRemovedOwnerStopsBeforeVoting()throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network(5,ReplicationBounds.defaults(),V53NativeDispatchTest.BUDGET,this::prepare,true)) {
            boolean success=false;
            try {
                var removed=n.owners.get(4);
                try(var round=round(n,4)) {
                    var error=assertThrows(IllegalArgumentException.class,round::startDiscovered);
                    assertEquals("native round local member not eligible for activation",error.getMessage());
                    assertEquals(MembershipRoundDriver.State.FAILED,round.state());assertThrows(IllegalArgumentException.class,round::readiness);
                    assertEquals(7L,removed.activationContext().cut.get("index"));assertFalse(removed.activationContext().voters().contains("node-5"));
                    assertTrue(n.wire.stream().map(row->MembershipWire.decode(Base64.getDecoder().decode((String)row.get("request")),FRAME))
                            .filter(r->object(r.value().get("sender")).get("node").equals("node-5"))
                            .noneMatch(r->Set.of("PREPARE","SELECTED","ACCEPT","PROOF","PUBLISH").contains(r.kind())));
                }
                try(var round=round(n,3)) {
                    assertEquals("PUBLISH_ACK",round.startDiscovered().kind());round.readiness();
                    var active=n.owners.get(3);assertEquals(8L,active.activationContext().cut.get("index"));
                    assertEquals(List.of("node-1","node-2","node-3","node-4"),list(active.activationContext().view.get("old")));
                    byte[] data;
                    try(var encoder=new ReplicaApplication<>(builder().configuration(),n.f.request.targets().get(3).materialization(),n.bounds)) {
                        data=MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(207,"discovered-survivor"))));
                    }
                    round.submit("DATA",data);round.readiness();assertEquals(9L,active.activationContext().cut.get("index"));
                    for(int i:List.of(0,1,3))assertEquals(active.activationContext().cut,n.owners.get(i).activationContext().cut);
                    assertEquals(7L,removed.activationContext().cut.get("index"));
                }
                success=true;
            }finally {
                Files.write(n.f.raw.resolve("discovered-transition-result.json"),canonical(Map.of("status",success?"PASS":"FAIL",
                        "profile","5-to-4-remove","staleSurvivor","node-4","removed","node-5","publicRuntime",false,
                        "autonomousElection",false,"independentReplay",false),8192));
            }
        }
    }
}
