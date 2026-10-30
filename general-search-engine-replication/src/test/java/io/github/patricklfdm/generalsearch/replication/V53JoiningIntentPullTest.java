package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional byte/link fixtures. They test receiver validation and lifetime,
 * not native force ownership, physical replay or a joined checkpoint vote. */
class V53JoiningIntentPullTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(30);
    static Map<String,Object> body(MembershipCapsule before,V53ContextFixture history,MembershipIdentity peer,MembershipIdentity learner) {
        var row=MembershipLearnerProgressAccess.operation(before.context,learner);
        var step=history.steps.get(5);var after=V53CapsuleFixture.fromHistory(history,6).verify();
        var records=new TreeMap<String,String>();
        for(String kind:List.of("ENTRY","ACCEPT","PROOF","CERTIFICATE"))
            records.put(kind,Base64.getEncoder().encodeToString(history.inventory.get(step.get(kind.toLowerCase(Locale.ROOT)))));
        records.put("CATALOG",Base64.getEncoder().encodeToString(history.inventory.get(step.get("catalogAfter"))));
        var edge=object(list(after.packet.capsule().value().get("items")).getLast());
        records.put("CHECKPOINT",Base64.getEncoder().encodeToString(after.packet.objectBytes((String)edge.get("statement"))));
        var entry=decode(Base64.getDecoder().decode(records.get("ENTRY")),"records","ENTRY");
        return Map.of("schema","gse-v53-joining-intent-metadata/1.3","root",before.context.root,
                "owner",MembershipBootstrapSeed.identity(peer),"learner",MembershipBootstrapSeed.identity(learner),
                "request",row.get("request"),"parent",MembershipRetentionIntent.anchor(before.terminal()),
                "target",MembershipRetentionIntent.anchor(after.terminal()),"records",records,
                "payload",Base64.getEncoder().encodeToString(history.inventory.get(entry.value().get("payload"))));
    }
    static Decoded answer(Decoded request,byte[] content) {
        var payload=object(request.value().get("payload"));String kind;Map<String,Object> result;
        if(request.kind().equals("TRANSFER_COMMIT")){kind="TRANSFER_COMMIT";result=payload;}
        else if(number(request.value().get("sequence"))==1) {
            kind="SOURCE_OFFER";result=Map.of("id",payload.get("id"),"kind","RECORD","bytes",(long)content.length,"digest",hash(content));
        }else {
            int offset=Math.toIntExact(number(payload.get("offset")));byte[] part=Arrays.copyOfRange(content,offset,Math.min(content.length,offset+1973));
            kind="CHUNK";result=Map.of("action","DATA","id",payload.get("id"),"offset",(long)offset,
                    "bytes",Base64.getEncoder().encodeToString(part),"digest",hash(part));
        }
        return V53LearnerDiscoveryTest.response(request,kind,result);
    }
    static final class Fixture implements AutoCloseable {
        final V53LearnerDiscoveryTest.Fixture f;
        final Decoded receipt;
        final Map<String,Object> body;
        final List<Decoded> requests=new ArrayList<>();
        final List<Long> deadlines=new ArrayList<>();
        final AtomicBoolean live=new AtomicBoolean(true);
        byte[] content;
        Fixture(int size,String change) {
            f=new V53LearnerDiscoveryTest().new Fixture(size,change,5);
            var row=MembershipLearnerProgressAccess.operation(f.capsule.context,f.request.identity());
            receipt=decode(encode("records","LEARNER",Map.of("root",f.capsule.context.root,"receipt",row.get("receipt"))),"records","LEARNER");
            body=body(f.capsule,f.fixture.source,f.peer,f.request.identity());
            content=canonical(body,MembershipJoiningIntentMetadata.MAXIMUM);
        }
        Fixture(){this(3,"ADD");}
        MembershipJoiningIntentPull pull(MembershipSourcePull.Link link)throws IOException{return pull(link,f.resources);}
        MembershipJoiningIntentPull pull(MembershipSourcePull.Link link,MembershipResources resources)throws IOException {
            return new MembershipJoiningIntentPull(f.request,f.peer,f.capsule,receipt,resources,V53TransferServiceTest.bound(2),
                    (peer,request,kind,deadline)->{requests.add(request);deadlines.add(deadline);return link.exchange(peer,request,kind,deadline);},
                    ()->{if(!live.get())throw new IOException("original parent revoked");},f.clock::get,0,BUDGET);
        }
        Decoded answer(Decoded request) {
            var payload=object(request.value().get("payload"));
            if(number(request.value().get("sequence"))==1)
                assertTrue(MembershipJoiningIntentExport.reference(f.capsule.context,f.request.identity(),(String)payload.get("digest")));
            return V53JoiningIntentPullTest.answer(request,content);
        }
        CompletableFuture<Decoded> normal(MembershipIdentity p,Decoded r,String k,long d){return CompletableFuture.completedFuture(answer(r));}
        MembershipJoiningIntentMetadata inspect(byte[] bytes){return MembershipJoiningIntentMetadata.inspect(f.request,f.peer,f.capsule,receipt,bytes);}
        @Override public void close(){f.close();}
    }
    @ParameterizedTest @CsvSource({"3,ADD","4,ADD","3,REPLACE","4,REPLACE","5,REPLACE"})
    void exactMetadataForEveryJoiningProfileIsNotPublication(int size,String kind)throws Exception {
        try(var f=new Fixture(size,kind);var pull=f.pull(f::normal)) {
            var before=f.f.capsule.terminal();var result=pull.fetch();assertSame(result,pull.metadata());
            assertArrayEquals(f.content,result.bytes());assertEquals("INTENT",result.record("ENTRY").value().get("kind"));
            assertEquals(before,f.f.capsule.terminal());assertEquals(Set.of(BUDGET),new HashSet<>(f.deadlines));
            assertEquals(1,f.requests.stream().filter(r->r.kind().equals("TRANSFER_COMMIT")).count());
            assertTrue(f.f.resources.usage().queued()>=3L*f.content.length);
            byte[] bytes=result.bytes();bytes[0]^=1;assertArrayEquals(f.content,pull.metadata().bytes());
            assertThrows(IllegalArgumentException.class,pull::fetch);pull.close();assertThrows(IllegalArgumentException.class,pull::metadata);
        }
    }
    @ParameterizedTest @ValueSource(strings={"schema","root","owner","learner","request","parent","target","extra",
            "missing-record","extra-record","payload","entry","proof","quorum","catalog","checkpoint","base64","canonical"})
    void alteredOriginalsCannotBecomeMetadata(String mode)throws Exception {
        try(var f=new Fixture()) {
            var b=object(V53ContextFixture.mutable(f.body));var records=object(b.get("records"));
            switch(mode) {
                case "schema" -> b.put("schema","other");
                case "root" -> b.put("root","a".repeat(64));
                case "owner","learner" -> object(b.get(mode)).put("storage",UUID.randomUUID().toString());
                case "request" -> object(b.get("request")).put("number",2L);
                case "parent","target" -> object(b.get(mode)).put("application","a".repeat(64));
                case "extra" -> b.put("extra",true);
                case "missing-record" -> records.remove("ACCEPT");
                case "extra-record" -> records.put("CHECKPOINT_ACK",records.get("ENTRY"));
                case "payload" -> b.put("payload",Base64.getEncoder().encodeToString(canonical(Map.of("number",1L),8192)));
                case "base64" -> records.put("ENTRY",records.get("ENTRY")+"!");
                case "canonical" -> { }
                default -> {
                    String kind=switch(mode){case "entry"->"ENTRY";case "proof"->"PROOF";case "quorum"->"CERTIFICATE";case "catalog"->"CATALOG";default->"CHECKPOINT";};
                    var v=object(V53ContextFixture.mutable(decode(Base64.getDecoder().decode((String)records.get(kind)),"records",kind).value()));
                    switch(mode) {
                        case "entry" -> v.put("previous","a".repeat(64));
                        case "proof" -> v.put("entry","a".repeat(64));
                        case "quorum" -> {
                            var newcomer=MembershipBootstrapSeed.identity(f.f.request.identity());
                            String proof=decode(Base64.getDecoder().decode((String)records.get("PROOF")),"records","PROOF").digest();
                            var witness=Map.of("voter",newcomer.get("node"),"incarnation",newcomer.get("storage"),"receipt",hash(canonical(
                                    Map.of("root",f.f.capsule.context.root,"voter",newcomer.get("node"),"incarnation",newcomer.get("storage"),"phase","PROOF","record",proof),2048)));
                            v.put("proofs",List.of(list(v.get("proofs")).get(1),witness));
                        }
                        case "catalog" -> v.put("applicationSequence",number(v.get("applicationSequence"))+1);
                        case "checkpoint" -> v.put("scope","RANGE");
                    }
                    records.put(kind,Base64.getEncoder().encodeToString(encode("records",kind,v)));
                }
            }
            f.content=canonical(b,MembershipJoiningIntentMetadata.MAXIMUM);
            if(mode.equals("canonical"))f.content=(new String(f.content,java.nio.charset.StandardCharsets.UTF_8)+" ").getBytes(java.nio.charset.StandardCharsets.UTF_8);
            Class<? extends RuntimeException> rejected=mode.equals("canonical")?ReplicationException.class:IllegalArgumentException.class;
            assertThrows(rejected,()->f.inspect(f.content));
            try(var pull=f.pull(f::normal)){assertThrows(rejected,pull::fetch);}
            assertTrue(f.requests.stream().noneMatch(r->r.kind().equals("TRANSFER_COMMIT")));
        }
    }
    @ParameterizedTest @ValueSource(strings={"offer","chunk","commit"})
    void lostRepliesRetryTheSameBytesAndOriginalDeadline(String point)throws Exception {
        try(var f=new Fixture()) {
            var count=new AtomicInteger();var retried=new ArrayList<Decoded>();
            try(var pull=f.pull((p,r,k,d)->{
                boolean selected=switch(point){case "offer"->number(r.value().get("sequence"))==1;case "chunk"->number(r.value().get("sequence"))==2;default->r.kind().equals("TRANSFER_COMMIT");};
                if(selected){retried.add(r);if(count.incrementAndGet()<3)return CompletableFuture.failedFuture(V53LearnerDiscoveryTest.lost());}
                return f.normal(p,r,k,d);
            })){pull.fetch();}
            assertEquals(3,retried.size());assertEquals(1,retried.stream().map(Decoded::digest).distinct().count());
            assertEquals(Set.of(BUDGET),new HashSet<>(f.deadlines));
        }
    }
    @Test void permanentFailureAndRetryExhaustionStopWithoutLeaking()throws Exception {
        for(var reason:MembershipTransport.Reason.values())try(var f=new Fixture();var pull=f.pull((p,r,k,d)->
                CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"injected",null)))) {
            assertThrows(MembershipTransport.Failure.class,pull::fetch);
            assertEquals(Set.of(MembershipTransport.Reason.IO,MembershipTransport.Reason.DEADLINE).contains(reason)?3:1,f.requests.size());
            assertEquals(0,f.f.resources.usage().leases());assertThrows(IllegalArgumentException.class,pull::metadata);
        }
    }
    @ParameterizedTest @ValueSource(strings={"offer-size","offer-id","offer-kind","chunk-offset","chunk-empty","chunk-hash","reply-sequence","commit-digest"})
    void badExchangeCannotComplete(String mode)throws Exception {
        try(var f=new Fixture();var pull=f.pull((p,r,k,d)->{
            var answer=f.answer(r);var v=new TreeMap<>(answer.value());var payload=new TreeMap<>(object(v.get("payload")));
            if(k.equals("SOURCE_OFFER"))switch(mode) {
                case "offer-size" -> payload.put("bytes",(long)MembershipJoiningIntentMetadata.MAXIMUM+1);
                case "offer-id" -> payload.put("id",UUID.randomUUID().toString());
                case "offer-kind" -> payload.put("kind","IMAGE");
                case "reply-sequence" -> v.put("sequence",number(v.get("sequence"))+1);
            }
            if(k.equals("CHUNK"))switch(mode) {
                case "chunk-offset" -> payload.put("offset",number(payload.get("offset"))+1);
                case "chunk-empty" -> {payload.put("bytes","");payload.put("digest",hash(new byte[0]));}
                case "chunk-hash" -> payload.put("digest","a".repeat(64));
            }
            if(k.equals("TRANSFER_COMMIT") && mode.equals("commit-digest"))payload.put("digest","a".repeat(64));
            v.put("payload",payload);return CompletableFuture.completedFuture(decode(encode("wire",answer.kind(),v),"wire",answer.kind()));
        })) {assertThrows(IllegalArgumentException.class,pull::fetch);assertEquals(0,f.f.resources.usage().leases());}
    }
    @Test void sharedCapacityIsReservedBeforeReadingContent()throws Exception {
        var pool=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,8192);
        try(var f=new Fixture();var pull=f.pull(f::normal,pool)) {
            assertTrue(3L*f.content.length>8192);assertThrows(IllegalArgumentException.class,pull::fetch);
            assertEquals(1,f.requests.size());assertEquals(0,pool.usage().leases());
        }
    }
    @Test void expiredOrRevokedParentCannotPublishLateBytesOrKeepAReadableResult()throws Exception {
        for(String mode:List.of("expired","revoked"))try(var f=new Fixture();var pull=f.pull((p,r,k,d)->{
            var result=f.normal(p,r,k,d);if(mode.equals("expired"))f.f.clock.set(BUDGET);else f.live.set(false);return result;
        })) {assertThrows(Exception.class,pull::fetch);assertEquals(1,f.requests.size());assertEquals(0,f.f.resources.usage().leases());}
        try(var f=new Fixture();var pull=f.pull(f::normal)){pull.fetch();f.live.set(false);assertThrows(IOException.class,pull::metadata);}
    }
    @Test void closeCancelsAnOutstandingExchange()throws Exception {
        try(var f=new Fixture()) {
            var waiting=new CompletableFuture<Decoded>();var entered=new CountDownLatch(1);
            try(var pull=f.pull((p,r,k,d)->{entered.countDown();return waiting;})) {
                var done=new CompletableFuture<Throwable>();var worker=new Thread(()->{try{pull.fetch();done.complete(null);}catch(Throwable error){done.complete(error);}});
                worker.start();try{assertTrue(entered.await(5,TimeUnit.SECONDS));pull.close();assertInstanceOf(IOException.class,done.get(5,TimeUnit.SECONDS));}
                finally{pull.close();worker.join(5000);}
                assertFalse(worker.isAlive());assertTrue(waiting.isCancelled());assertEquals(0,f.f.resources.usage().leases());
            }
        }
    }
    @Test void actualPreparedOwnerAndCompleteProgressGuardTheReadOnlyContact()throws Exception {
        var learner=new V53LearnerMaterializationTest();learner.temp=temp;
        var helper=new V53LearnerProgressNetworkTest();helper.temp=temp;
        try(var f=learner.new Fixture(3,"ADD");var typed=f.prepare(e->{})) {
            var head=typed.retainGeneration();var original=f.source.fixture.fixture;
            var sealed=V53CapsuleFixture.fromHistory(original.source,5);
            try(var source=helper.new Peer(sealed,true)) {
                byte[] metadata=canonical(body(source.owner.activationCapsule(),original.source,source.owner.activationIdentity(),f.source.request.identity()),MembershipJoiningIntentMetadata.MAXIMUM);
                var traces=ConcurrentHashMap.<String>newKeySet();
                try(var transport=new MembershipTransport(source.owner,f.config.bounds(),source.server,(sender,request)->{
                    if(request.kind().equals("STATUS_PROBE"))return MembershipDiscovery.answer(source.owner.activationContext(),source.owner.activationIdentity(),sender,request);
                    var payload=object(request.value().get("payload"));String trace=(String)request.value().get("trace");
                    if(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1
                            && MembershipJoiningIntentExport.reference(source.owner.activationContext(),sender,(String)payload.get("digest")))traces.add(trace);
                    // Conditional certificate bytes exercise the actual client
                    // and live owner guard, not the source's native capability.
                    return traces.contains(trace)?answer(request,metadata):source.service.handle(sender,request);
                },MembershipTransport.Events.NONE)) {
                    var before=V53ReplayFilesTest.files(f.source.request.replicaDirectory());var prepared=V53ReplayFilesTest.files(f.typed());
                    var usage=f.source.client.usage();MembershipJoiningIntentPull pull;
                    try(var progress=new MembershipLearnerProgress(head,source.owner.activationIdentity(),f.config.bounds(),MembershipTransport.Events.NONE,
                            System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
                        assertThrows(IllegalArgumentException.class,progress::joiningMetadata);
                        progress.fetch(f.base.resolve("sealed-progress"));pull=progress.joiningMetadata();
                        assertArrayEquals(metadata,pull.fetch().bytes());assertThrows(IllegalArgumentException.class,progress::joiningMetadata);
                        assertEquals("SEALED",MembershipLearnerProgressAccess.operation(progress.source().capsule.context,f.source.request.identity()).get("phase"));
                        progress.close();assertThrows(IllegalArgumentException.class,pull::metadata);
                    }
                    assertEquals(usage,f.source.client.usage());assertEquals(before,V53ReplayFilesTest.files(f.source.request.replicaDirectory()));
                    assertEquals(prepared,V53ReplayFilesTest.files(f.typed()));head.check();assertFalse(Files.exists(f.config.materialization().directory()));
                }
            }
        }
    }
}
