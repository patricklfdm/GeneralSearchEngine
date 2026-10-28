package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** A native authority-changing slot must ACK under its original governing view,
 * while its old activation scope must never grant another ordinary operation. */
class V53AuthorityTransitionTest {
    @TempDir Path temp;
    @Test void nativeIntentReturnsItsOriginalAckAndEndsOldActivationAuthority()throws Exception {transition("INTENT");}
    @Test void nativeFinalReturnsItsOriginalAckAndRequiresFreshStableActivation()throws Exception {transition("FINAL");}
    private void transition(String kind)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;var b=ReplicationBounds.defaults();
        var bounds=new ReplicationBounds(b.maxFrameBytes(),b.maxEntriesPerAppend(),b.maxInFlightPerPeer(),b.maxPendingClientOperations(),
                b.maxRetryAttempts(),30_000,b.retryBackoffMillis(),b.snapshotChunkBytes(),b.maxRetainedLogBytes(),b.maxSnapshotStagingBytes());
        try(var n=helper.new Network(4,bounds,f->{
            var walk=new V53AdmittedCrossViewTest.Walk(f);
            var request=Map.of("root",f.result.root().manifestDigest(),"expected",walk.current().authority(),"number",1L,"kind","REMOVE",
                    "target",f.request.targets().subList(0,3).stream().map(t->MembershipBootstrapSeed.identity(t.identity())).toList());
            walk.publish("RESERVE",Map.of("request",request));walk.publish("PREPARE",Map.of("number",1L,"revision",1L));
            walk.publish("READY",V53ContextFixture.map("number",1L,"receipt",null));walk.publish("SEAL",Map.of("number",1L));
            if(kind.equals("FINAL")) {
                var operation=object(list(walk.current().catalog.get("results")).getLast());
                walk.publish("INTENT",Map.of("sealed",V53ContextFixture.map("request",operation.get("request"),
                        "prepared",operation.get("prepared"),"receipt",operation.get("receipt"))));
            }
        })) {
            long started=System.nanoTime();n.activate();var own=n.owners.getFirst();var context=own.activationContext();
            var operation=object(list(context.catalog.get("results")).getLast());
            byte[] payload=canonical(kind.equals("INTENT")?Map.of("sealed",V53ContextFixture.map("request",operation.get("request"),
                    "prepared",operation.get("prepared"),"receipt",operation.get("receipt"))):Map.of("binding",operation.get("binding")),8192);
            long index=number(context.cut.get("index"))+1;
            var entry=decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),
                    "index",index,"previous",context.cut.get("entry"),"origin",n.ballot,"kind",kind,"payload",hash(payload))),"records","ENTRY");
            n.events.add(Map.of("node","node-1","event","SLOT_BEGIN","index",entry.value().get("index")));
            var publication=new MembershipGrantJournal.Publication[1];
            try(var driver=new MembershipSlotDriver(own,n.endpoints.getFirst(),n.resources.getFirst(),bounds,n.transports.getFirst(),
                    System::nanoTime,started,V53NativeDispatchTest.BUDGET,builder().configuration(),n.f.request.targets().getFirst().materialization(),
                    (event,record,voters)->{
                        if(event.equals("APPLIED"))publication[0]=own.publication(own.voting(n.resources.getFirst()).application().orElseThrow());
                        n.events.add(Map.of("node","node-1","event","DRIVER_"+event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                        if(event.equals("APPLIED") || event.equals("PUBLISHED"))try{n.f.snapshot(event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));}
                        catch(Exception error){throw new java.io.IOException(error);}
                    })) {
                var ack=driver.run(entry,payload);assertEquals("PUBLISH_ACK",ack.kind());assertEquals(context.authority(),ack.value().get("view"));
                assertNotEquals(context.authority(),own.activationContext().authority());
                int firstPublish=-1,quorums=0;
                for(var event:n.events){
                    if(event.get("event").equals("DRIVER_FUTURE_QUORUM_COMPLETE")){assertEquals(-1,firstPublish);quorums++;}
                    if(event.get("event").equals("PUBLICATION_SEND_BOUNDARY"))firstPublish=1;
                }
                assertEquals(n.voters.size()-1,quorums);assertEquals(1,firstPublish);
                assertTrue(n.failures.stream().noneMatch(v->v.get("kind").equals("PUBLISH")),n.failures.toString());
                for(int i:n.voters) {
                    var after=n.owners.get(i).activationContext();
                    if(kind.equals("INTENT"))assertNotNull(after.view.get("operation"));else assertNull(after.view.get("operation"));
                    assertEquals(index,after.cut.get("index"));
                    assertEquals("activation view changed",assertThrows(IllegalArgumentException.class,n.endpoints.get(i)::checkInstalled).getMessage());
                }
                var fields=new TreeMap<>(ack.value());fields.put("payload",Map.of("certificate",object(ack.value().get("payload")).get("certificate")));
                var duplicate=decode(encode("wire","PUBLISH",fields),"wire","PUBLISH");
                assertArrayEquals(ack.bytes(),n.endpoints.getFirst().handle(own.activationIdentity(),duplicate).bytes());
                fields.put("payload",Map.of("certificate","0".repeat(64)));var wrong=decode(encode("wire","PUBLISH",fields),"wire","PUBLISH");
                assertThrows(IllegalArgumentException.class,()->n.endpoints.getFirst().handle(own.activationIdentity(),wrong));
                var original=publication[0];var checkpoint=original.applied.endorsement().acknowledgement();
                assertThrows(IllegalArgumentException.class,()->own.exportPublishedCheckpoint(original,own.originalBasis().orElseThrow().digest(),
                        System::nanoTime,started,V53NativeDispatchTest.BUDGET));
                var other=new TreeMap<>(checkpoint.value());other.put("voter","node-2");other.put("incarnation",n.owners.get(1).activationIdentity().storageId().toString());
                var otherAck=decode(encode("records","CHECKPOINT_ACK",other),"records","CHECKPOINT_ACK");
                assertThrows(IllegalArgumentException.class,()->own.exportPublishedCheckpoint(original,otherAck.digest(),System::nanoTime,started,V53NativeDispatchTest.BUDGET));
                try(var exported=own.exportPublishedCheckpoint(original,checkpoint.digest(),System::nanoTime,started,V53NativeDispatchTest.BUDGET)) {
                    assertEquals(context.authority(),exported.context().authority());
                    assertArrayEquals(checkpoint.bytes(),exported.read(checkpoint.digest(),0,8192));
                    var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);own.observeCurrent(higher);
                    assertThrows(IllegalArgumentException.class,()->exported.read(checkpoint.digest(),0,8192));
                    assertThrows(IllegalArgumentException.class,()->n.endpoints.getFirst().handle(own.activationIdentity(),duplicate));
                }
            }
            Files.write(n.f.raw.resolve("authority-result.json"),canonical(Map.of("status","PASS","kind",kind,"publicReady",false),4096));
            System.out.println("v53AuthorityTransition=PASS kind="+kind+" raw="+n.f.raw.toAbsolutePath());
        }
    }
}
