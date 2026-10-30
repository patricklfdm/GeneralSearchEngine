package io.github.patricklfdm.generalsearch.replication;

import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Actual bootstrap/typed learner/old-quorum INTENT originals. Metadata receipt
 * is not a joined checkpoint ACK; that next native path remains separate. */
class V53JoiningIntentExportTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.MINUTES.toNanos(12);
    record Input(Decoded entry,byte[] payload) {}
    static Input input(V53NativeDispatchTest.Network n,String kind,Object command)throws Exception {
        var context=n.owners.getFirst().activationContext();byte[] payload=canonical(command,8192);
        return new Input(decode(encode("records","ENTRY",Map.of("root",context.root,"authority",context.authority(),
                "index",number(context.cut.get("index"))+1,"previous",context.cut.get("entry"),"origin",n.ballot,
                "kind",kind,"payload",hash(payload))),"records","ENTRY"),payload);
    }
    static void publish(V53NativeDispatchTest.Network n,String kind,Object command)throws Exception {
        var input=input(n,kind,command);
        try(var driver=new MembershipSlotDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,
                n.transports.getFirst(),System::nanoTime,System.nanoTime(),BUDGET,builder().configuration(),
                n.f.request.targets().getFirst().materialization(),MembershipSlotDriver.Events.NONE)) {
            assertEquals("PUBLISH_ACK",driver.run(input.entry,input.payload).kind());
        }
    }
    static Decoded initial(MembershipLearnerRequest request,MembershipIdentity peer,Map<String,Object> cut) {
        return frame(request,peer,UUID.randomUUID(),1,"CHUNK",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST",
                "offset",0L,"digest",MembershipJoiningIntentExport.reference(request,cut),"bytes",""));
    }
    static Decoded frame(MembershipLearnerRequest request,MembershipIdentity peer,UUID trace,long sequence,String kind,Map<String,Object> payload) {
        return decode(encode("wire",kind,Map.of("root",request.root().manifestDigest(),"view",request.change().expectedConfigurationDigest(),
                "ballot",MembershipLearnerDiscovery.correlation(request.identity()),"sender",MembershipBootstrapSeed.identity(request.identity()),
                "recipient",MembershipBootstrapSeed.identity(peer),"trace",trace.toString(),"sequence",sequence,"payload",payload)),"wire",kind);
    }
    static Decoded exchange(MembershipTransport contact,MembershipIdentity peer,Decoded request,String kind)throws Exception {
        var response=contact.exchange(peer,request,kind,System.nanoTime()+TimeUnit.SECONDS.toNanos(30)).get(35,TimeUnit.SECONDS);
        MembershipWire.correlated(request,response,kind);assertEquals(kind,response.kind());return response;
    }
    static byte[] fetch(MembershipTransport contact,MembershipLearnerRequest learner,MembershipIdentity peer,Decoded first)throws Exception {
        var offer=exchange(contact,peer,first,"SOURCE_OFFER");var content=object(offer.value().get("payload"));
        assertEquals("RECORD",content.get("kind"));assertEquals(object(first.value().get("payload")).get("id"),content.get("id"));
        assertArrayEquals(offer.bytes(),exchange(contact,peer,first,"SOURCE_OFFER").bytes());
        var out=new java.io.ByteArrayOutputStream();long sequence=1;var trace=UUID.fromString((String)first.value().get("trace"));
        while(out.size()<number(content.get("bytes"))) {
            var request=frame(learner,peer,trace,++sequence,"CHUNK",Map.of("id",content.get("id"),"action","REQUEST",
                    "offset",(long)out.size(),"digest",content.get("digest"),"bytes",""));
            var response=exchange(contact,peer,request,"CHUNK");var payload=object(response.value().get("payload"));
            assertEquals((long)out.size(),payload.get("offset"));assertEquals(content.get("id"),payload.get("id"));
            byte[] bytes=Base64.getDecoder().decode((String)payload.get("bytes"));assertEquals(hash(bytes),payload.get("digest"));out.writeBytes(bytes);
        }
        assertEquals(number(content.get("bytes")),out.size());assertEquals(hash(out.toByteArray()),content.get("digest"));
        var last=frame(learner,peer,trace,++sequence,"TRANSFER_COMMIT",Map.of("id",content.get("id"),"digest",content.get("digest")));
        var done=exchange(contact,peer,last,"TRANSFER_COMMIT");
        assertArrayEquals(done.bytes(),exchange(contact,peer,last,"TRANSFER_COMMIT").bytes());return out.toByteArray();
    }
    @Test void minimalOldMajorityCanServeOriginalIntentBeforeJointCheckpointExists()throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;var network=new V53NativeDispatchTest();network.temp=temp;
        try(var n=network.new Network(3,helper.controlBounds(),BUDGET,f->{
            for(var target:f.request.targets())try(var owner=f.open(target,"initialize-learners")){owner.initializeLearnerRetention();}
        },true);var round=helper.driver(n,MembershipRoundDriver.Events.NONE,BUDGET)) {
            // The short Network.activate helper fixes a 180-second campaign.
            // This complete typed-learner history uses one declared 12-minute
            // owner lifetime from its start, without extending any RPC timeout.
            n.transports.get(2).close();round.start();assertEquals(List.of(0,1),n.voters);
            int port;try(var socket=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=socket.getLocalPort();}
            var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
            var targets=new ArrayList<MembershipIdentity>();n.f.request.targets().forEach(t->targets.add(t.identity()));targets.add(joining);
            var owner=n.owners.getFirst();var resources=n.resources.getFirst();
            var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),owner.activationContext().authority(),MembershipChangeKind.ADD,targets);
            var request=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("learner"),temp.resolve("operation"));
            round.submit("RESERVE",canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192));
            round.submit("PREPARE",canonical(Map.of("number",1L,"revision",1L),8192));
            System.out.println("v53JoiningIntentStage=prepared");
            var pool=new MembershipResources(512*MembershipResources.MIB);
            var config=new MembershipReplicaConfig<>(request.root(),joining,List.of(),request.replicaDirectory(),storage(temp.resolve("core"),2),
                    n.bounds,AutomaticLeadershipPolicy.forBounds(n.bounds));
            try(var source=new MembershipLearnerSource(request,targets.getFirst(),pool,n.bounds,MembershipTransport.Events.NONE,
                    ()->{},System::nanoTime,System.nanoTime(),BUDGET)) {
                source.fetch(temp.resolve("receiving"));var plan=source.plan(e->{});
                try(var store=source.admit(plan,e->{})) {
                    source.close();
                    try(var typed=MembershipLearnerMaterialization.prepare(MembershipLearnerPreparation.from(store,1),builder().configuration(),config,e->{})) {
                        round.submit("READY",canonical(Map.of("number",1L,"receipt",typed.receipt().value().get("receipt")),8192));
                        publish(n,"SEAL",Map.of("number",1L));var before=owner.activationContext();var first=initial(request,targets.getFirst(),before.cut);
                        System.out.println("v53JoiningIntentStage=sealed");
                        // A SEALED catalog alone cannot mint an original pending source.
                        assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,first,resources,
                                System::nanoTime,System.nanoTime(),BUDGET));
                        var row=object(list(before.catalog.get("results")).getLast());var sealed=new TreeMap<String,Object>();
                        for(String field:List.of("request","prepared","receipt"))sealed.put(field,row.get(field));
                        var next=input(n,"INTENT",Map.of("sealed",sealed));n.endpoints.getFirst().maintainInstalled();
                        owner.acceptCurrent(next.entry,next.payload,builder().configuration(),n.f.request.targets().getFirst().materialization());
                        assertThrows(IllegalArgumentException.class,()->owner.joiningIntent(joining));
                        var certificate=n.apply(owner.voting(resources).record("ACCEPT").orElseThrow());
                        var applied=owner.voting(resources).application().orElseThrow();
                        var other=n.owners.get(1).voting(n.resources.get(1)).application().orElseThrow();
                        assertEquals(List.of("node-1","node-2"),list(certificate.value().get("proofs")).stream().map(v->object(v).get("voter")).toList());
                        // Old majority certificate is real, but old 2/3 alone is
                        // not new 3/4. Keep that required refusal unchanged.
                        assertThrows(IllegalArgumentException.class,()->applied.plan().complete(
                                List.of(applied.endorsement().acknowledgement(),other.endorsement().acknowledgement()),
                                Set.of(applied.endorsement().owned(),other.endorsement().owned())));
                        assertSame(before,owner.activationContext());assertFalse(before.voters().contains("node-4"));
                        var files=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
                        var learnerFiles=V53ReplayFilesTest.files(request.operationDirectory());
                        var wire=new ArrayList<Map<String,Object>>();
                        try(var contact=MembershipTransport.learnerJoiningIntent(request,new MembershipDiscovery.Hint(targets.getFirst(),before.cut,false),n.bounds,pool,(event,q,a)->{
                            if(event.equals("AFTER_RESPONSE_READ"))wire.add(V53SelectedPullTest.wire(q,a));
                        })) {
                            var forbidden=new TreeMap<>(first.value());var p=new TreeMap<>(object(first.value().get("payload")));
                            p.put("digest",MembershipLearnerDiscovery.reference(request));forbidden.put("payload",p);
                            assertEquals(MembershipTransport.Reason.PROTOCOL,V53MembershipTransportTest.failure(contact.exchange(targets.getFirst(),
                                    decode(encode("wire","CHUNK",forbidden),"wire","CHUNK"),"SOURCE_OFFER",System.nanoTime()+BUDGET)).reason);
                            var bytes=fetch(contact,request,targets.getFirst(),first);var value=object(parse(bytes,FRAME));var records=object(value.get("records"));
                            assertEquals("gse-v53-joining-intent-metadata/1.3",value.get("schema"));assertEquals(sealed.get("request"),value.get("request"));
                            assertEquals(MembershipRetentionIntent.anchor(owner.activationCapsule().terminal()),value.get("parent"));
                            assertEquals(MembershipBootstrapSeed.identity(joining),value.get("learner"));
                            assertEquals(Set.of("ENTRY","ACCEPT","PROOF","CERTIFICATE","CATALOG","CHECKPOINT"),records.keySet());
                            assertArrayEquals(certificate.bytes(),Base64.getDecoder().decode((String)records.get("CERTIFICATE")));
                            assertArrayEquals(next.entry.bytes(),Base64.getDecoder().decode((String)records.get("ENTRY")));
                            assertArrayEquals(next.payload,Base64.getDecoder().decode((String)value.get("payload")));
                            assertArrayEquals(applied.plan().catalog.bytes(),Base64.getDecoder().decode((String)records.get("CATALOG")));
                            assertArrayEquals(applied.plan().statement.bytes(),Base64.getDecoder().decode((String)records.get("CHECKPOINT")));
                            Files.write(n.f.raw.resolve("joining-intent.json"),bytes);
                        }
                        assertEquals(files,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
                        assertEquals(learnerFiles,V53ReplayFilesTest.files(request.operationDirectory()));assertSame(before,owner.activationContext());
                        guardChecks(n,request,first);
                        Files.write(n.f.raw.resolve("joining-intent-wire.json"),canonical(wire,8*1024*1024));
                        Files.write(n.f.raw.resolve("joining-intent-result.json"),canonical(Map.of("status","PASS","oldVoters",List.of("node-1","node-2"),
                                "nativeHistory",true,"typedLearner",true,"publishedJoint",false,"publicReady",false),4096));
                    }
                }
            }
            assertEquals(0,pool.usage().leases());
        }
    }
    private void guardChecks(V53NativeDispatchTest.Network n,MembershipLearnerRequest request,Decoded first)throws Exception {
        var owner=n.owners.getFirst();var resources=n.resources.getFirst();var joining=request.identity();
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
        while(n.transports.stream().anyMatch(t->{var u=t.usage();return u.outgoing()!=0 || u.incoming()!=0 || u.sockets()!=0;})) {
            assertTrue(System.nanoTime()<end,"native transfer drain before exact accounting");Thread.sleep(10);
        }
        var before=resources.usage();var wrong=new MembershipResources(512*MembershipResources.MIB);
        assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,first,wrong,System::nanoTime,0,BUDGET));
        assertEquals(0,wrong.usage().leases());
        assertThrows(IllegalArgumentException.class,()->owner.joiningIntent(n.owners.get(1).activationIdentity()));
        var changed=new TreeMap<>(first.value());changed.put("ballot",n.ballot);
        assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,decode(encode("wire","CHUNK",changed),"wire","CHUNK"),
                resources,System::nanoTime,System.nanoTime(),BUDGET));
        var expired=new AtomicLong(0);
        try(var export=new MembershipJoiningIntentExport(owner,joining,first,resources,expired::get,0,10)) {
            expired.set(10);assertThrows(IllegalArgumentException.class,export::references);
        }
        var exports=new ArrayList<MembershipJoiningIntentExport>();
        try {
            // The real maintenance service may still own current-generation
            // borrows. Fill the remaining shared capacity, not six new slots.
            for(int i=0;i<6;i++) {
                var at=resources.usage();
                try {exports.add(new MembershipJoiningIntentExport(owner,joining,first,resources,System::nanoTime,System.nanoTime(),BUDGET));}
                catch(IllegalArgumentException full) {
                    assertEquals("prefix export owner capacity",full.getMessage());assertEquals(at,resources.usage());break;
                }
            }
            assertFalse(exports.isEmpty());
            var full=resources.usage();
            assertThrows(IllegalArgumentException.class,()->new MembershipJoiningIntentExport(owner,joining,first,resources,System::nanoTime,System.nanoTime(),BUDGET));
            assertEquals(full,resources.usage());
        }finally{for(var export:exports)export.close();}
        assertEquals(before,resources.usage());
        try(var export=new MembershipJoiningIntentExport(owner,joining,first,resources,System::nanoTime,System.nanoTime(),BUDGET)) {
            var content=export.references().values().iterator().next();
            assertThrows(IllegalArgumentException.class,()->export.read("0".repeat(64),0,1));
            assertThrows(IllegalArgumentException.class,()->export.read(content.digest(),content.bytes(),1));
            var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(higher);
            assertThrows(IllegalArgumentException.class,export::references);
            assertThrows(IllegalArgumentException.class,()->export.read(content.digest(),0,1));
        }
    }
}
