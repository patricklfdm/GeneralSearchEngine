package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Whole native lifecycle producer. Same-process cold reopen is not SIGKILL;
 * independent multi-lifetime replay and the full process matrix remain gates. */
class V53NodeOwnerNetworkTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(180);
    @Test void nodeOwnsTcpStorageAndFreshBarrierAcrossColdReopen()throws Exception {
        Path raw=Files.createDirectories(Path.of("target/v53-node-owner/run-"+UUID.randomUUID()));
        System.out.println("v53NodeOwnerEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(raw,V53OwnedCrossViewTest.networkRequest(Files.createDirectory(temp.resolve("group")),3,false));
        f.ownedHistory=true;f.nativeApplication=true;
        for(var target:f.request.targets())try(var journal=f.open(target,"initialize-retention")){journal.initializePeerRetention();journal.initializeFutureRetention();}
        f.snapshot("before-network");
        var nodes=new ArrayList<MembershipNodeOwner<Integer,Doc>>();var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>());var installed=new AtomicInteger();
        var bounds=ReplicationBounds.defaults();
        class Factory {
            MembershipNodeOwner<Integer,Doc> make(int index,int incarnation)throws Exception {
                var target=f.request.targets().get(index);String name=target.identity().nodeId().value();
                Path scratch=temp.resolve("scratch-"+index);if(!Files.exists(scratch))Files.createDirectory(scratch);
                var config=new MembershipReplicaConfig<>(f.result.root(),target.identity(),f.request.targets().stream().map(MembershipBootstrapTarget::identity)
                        .filter(identity->!identity.equals(target.identity())).toList(),target.replicaDirectory(),target.materialization(),bounds,AutomaticLeadershipPolicy.forBounds(bounds));
                var hooks=new MembershipNodeOwner.Hooks(event->events.add(Map.of("node",name,"incarnation",incarnation,"event",event)),
                    (event,request,response)->{
                        if(event.equals("BEFORE_REQUEST_WRITE"))events.add(Map.of("node",name,"incarnation",incarnation,"event","NETWORK_SEND","request",request.digest(),"kind",request.kind(),"bytes",Base64.getEncoder().encodeToString(request.bytes())));
                        if(event.equals("AFTER_REQUEST_READ"))events.add(Map.of("node",name,"incarnation",incarnation,"event","NETWORK_REQUEST","request",request.digest(),"kind",request.kind()));
                        if(event.equals("BEFORE_REQUEST_WRITE") && request.kind().equals("PUBLISH"))events.add(Map.of("node",name,"event","PUBLICATION_SEND_BOUNDARY","request",request.digest()));
                        if(event.equals("AFTER_RESPONSE_READ"))events.add(Map.of("node",name,"incarnation",incarnation,"event","NETWORK_RECEIVED","kind",response.kind(),"response",response.digest()));
                        if(event.equals("BEFORE_RESPONSE_WRITE")) {
                            var row=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));row.put("withheld",false);wire.add(row);
                            events.add(Map.of("node",name,"incarnation",incarnation,"event","WIRE_RESPONSE","request",request.digest(),"response",response.digest()));
                        }
                    },(event,record)->{
                        events.add(Map.of("node",name,"incarnation",incarnation,"event","ROUND_"+event,"record",record.digest(),"bytes",Base64.getEncoder().encodeToString(record.bytes())));
                        try {
                            if(event.equals("INSTALLED")){int at=installed.incrementAndGet();Files.write(raw.resolve("selected-"+at+".gsr"),record.bytes());f.snapshot("installed-"+at);}
                        }catch(Exception error){throw new IOException(error);}
                    },(event,record,voters)->{
                        if(event.equals("FUTURE_QUORUM_COMPLETE"))events.add(Map.of("node",name,"event",event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                        if(event.equals("APPLIED") || event.equals("PUBLISHED"))try{f.snapshot(event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));}
                        catch(Exception error){throw new IOException(error);}
                    });
                var node=new MembershipNodeOwner<>(config,builder().configuration(),scratch.resolve("incoming"),scratch.resolve("outgoing"),System::nanoTime,BUDGET,hooks);
                nodes.add(node);node.open();events.add(Map.of("node",name,"incarnation",incarnation,"event","NODE_OPEN"));return node;
            }
            byte[] data(int id)throws Exception {
                try(var encoder=new ReplicaApplication<>(builder().configuration(),f.request.targets().getFirst().materialization(),bounds)) {
                    return MembershipApplicationReplay.data("ADD",encoder.documents("ADD",List.of(new Doc(id,"node-owner-"+id))));
                }
            }
        }
        var factory=new Factory();boolean success=false;
        try {
            var first=factory.make(0,1);factory.make(1,1);factory.make(2,1);
            assertThrows(IllegalArgumentException.class,first::readiness);var firstBarrier=first.start().await(180,TimeUnit.SECONDS);
            f.snapshot("first-ready");assertEquals("PUBLISH_ACK",first.submit("DATA",factory.data(100)).await(180,TimeUnit.SECONDS).kind());
            first.close();assertEquals(0,first.usage().leases());events.add(Map.of("node","node-1","incarnation",1,"event","NODE_CLOSED"));f.snapshot("before-reopen");
            var fresh=factory.make(0,2);assertEquals(MembershipAutomaticOwner.State.NEW,fresh.serviceState().orElseThrow());
            assertThrows(IllegalArgumentException.class,fresh::readiness);assertThrows(IllegalArgumentException.class,()->first.submit("DATA",new byte[0]));
            var secondBarrier=fresh.start().await(180,TimeUnit.SECONDS);assertNotEquals(firstBarrier.digest(),secondBarrier.digest());
            assertTrue(MembershipContext.compareBallot(object(secondBarrier.value().get("ballot")),object(firstBarrier.value().get("ballot")))>0);
            f.snapshot("second-ready");assertEquals("PUBLISH_ACK",fresh.submit("DATA",factory.data(101)).await(180,TimeUnit.SECONDS).kind());
            fresh.close();assertEquals(0,fresh.usage().leases());events.add(Map.of("node","node-1","incarnation",2,"event","NODE_CLOSED"));
            assertEquals(2,installed.get());
            var entries=events.stream().filter(v->v.get("event").equals("ROUND_SLOT_BEGIN")).map(v->decode(Base64.getDecoder().decode((String)v.get("bytes")),"records","ENTRY")).toList();
            assertEquals(List.of(1L,2L,3L,4L),entries.stream().map(v->v.value().get("index")).toList());
            assertEquals(List.of("BARRIER","DATA","BARRIER","DATA"),entries.stream().map(v->v.value().get("kind")).toList());success=true;
        }finally {
            IOException closing=null;
            for(var node:nodes.reversed())try{node.close();assertEquals(0,node.usage().leases());}
            catch(IOException error){if(closing==null)closing=error;else closing.addSuppressed(error);}
            Files.write(raw.resolve("wire.json"),canonical(wire,32*1024*1024));Files.write(raw.resolve("events.json"),canonical(events,16*1024*1024));
            f.snapshot("after-close");V53NativeApplicationTest.save(f);
            Files.write(raw.resolve("node-result.json"),canonical(Map.of("status","PARTIAL","producerPassed",success && closing==null,
                    "coldReopens",1,"barriers",2,"dataCalls",2,"physicalReplay",false,"processRestart",false,"phase3Complete",false,
                    "serviceBudgetNanos",BUDGET),4096));
            if(closing!=null)throw closing;
        }
    }
}
