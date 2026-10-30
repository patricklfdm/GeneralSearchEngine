package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.TestInfo;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real typed owner, storage, TCP and original ACK reads; old voting history is
 * a conditional fixture. This is not native JOINT publication or process death. */
class V53LearnerCheckpointEndpointTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.MINUTES.toNanos(3);
    @BeforeEach void announce(TestInfo info){System.out.println("v53JoiningCheckpointCase="+info.getTestMethod().orElseThrow().getName());}
    final class Fixture implements AutoCloseable {
        final V53LearnerPendingIntentTest.Fixture fixture;
        final MembershipLearnerPendingIntent pending;
        final MembershipResources.Usage baseline;
        final AtomicLong clock=new AtomicLong(System.nanoTime());
        final long started=clock.get();
        final MembershipCapsule source;
        final MembershipIdentity local,reader;
        final Map<String,Object> ballot;
        Fixture()throws Exception {this(e->{});}
        Fixture(MembershipBallotAllocator.Cut cut)throws Exception {
            var helper=new V53LearnerPendingIntentTest();helper.temp=temp;fixture=helper.new Fixture();
            baseline=fixture.f.local.source.client.usage();pending=fixture.retain(cut);fixture.server.close();
            source=pending.source();local=fixture.f.head.request().identity();reader=fixture.f.peer.owner.activationIdentity();
            ballot=object(pending.originals().record("CERTIFICATE").value().get("ballot"));
        }
        MembershipLearnerCheckpointEndpoint listen(MembershipTransport.Events events)throws Exception {
            return pending.listen(fixture.f.local.config.bounds(),events,clock::get,started,BUDGET);
        }
        MembershipTransport contact()throws Exception {
            return new MembershipTransport(source,reader,fixture.f.local.config.bounds(),fixture.f.peer.server,
                    (p,r)->{throw new IOException("test contact is read-only");},MembershipTransport.Events.NONE);
        }
        Decoded frame(UUID trace,long sequence,String kind,Map<String,Object> payload) {
            return MembershipActivation.frame(kind,source.context,reader,local,ballot,trace,sequence,payload);
        }
        Decoded expected()throws Exception {
            var statement=pending.originals().record("CHECKPOINT");
            return decode(encode("records","CHECKPOINT_ACK",Map.of("root",statement.value().get("root"),"voter",local.nodeId().value(),
                    "incarnation",local.storageId().toString(),"cut",statement.value().get("end"),"statement",statement.digest())),"records","CHECKPOINT_ACK");
        }
        Decoded first()throws Exception {
            return frame(UUID.randomUUID(),1,"CHUNK",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,
                    "digest",expected().digest(),"bytes",""));
        }
        Decoded finish(MembershipLearnerCheckpointEndpoint endpoint,Decoded first)throws Exception {
            var offer=endpoint.answer(reader,first);var payload=object(offer.value().get("payload"));
            var trace=UUID.fromString((String)first.value().get("trace"));
            var chunk=MembershipActivation.frame("CHUNK",source.context,reader,local,object(first.value().get("ballot")),trace,2,Map.of("id",payload.get("id"),"action","REQUEST","offset",0L,"digest",payload.get("digest"),"bytes",""));
            var content=object(endpoint.answer(reader,chunk).value().get("payload"));
            assertEquals(number(payload.get("bytes")),Base64.getDecoder().decode((String)content.get("bytes")).length);
            var commit=MembershipActivation.frame("TRANSFER_COMMIT",source.context,reader,local,object(first.value().get("ballot")),trace,3,Map.of("id",payload.get("id"),"digest",payload.get("digest")));
            assertEquals("TRANSFER_COMMIT",endpoint.answer(reader,commit).kind());return commit;
        }
        MembershipSourcePull.CheckpointReceipt fetch(MembershipSourcePull.Link link)throws Exception {
            var expected=expected();var statement=pending.originals().record("CHECKPOINT");
            try(var pull=new MembershipSourcePull(source,reader,local,ballot,UUID.randomUUID(),fixture.f.peer.server,fixture.f.local.config.bounds(),
                    link,()->{},System::nanoTime,System.nanoTime(),BUDGET)) {
                return pull.fetchCheckpointAcknowledgement(statement,expected);
            }
        }
        @Override public void close()throws Exception{pending.close();fixture.close();}
    }
    @Test void actualOwnerAckUsesTheExistingPullAndRetriesIdenticalLostReplies()throws Exception {
        try(var f=new Fixture();var endpoint=f.listen(MembershipTransport.Events.NONE);var contact=f.contact()) {
            var events=new ArrayList<Decoded>();var deadlines=new HashSet<Long>();var attempts=new HashMap<String,Integer>();
            var before=V53ReplayFilesTest.files(f.fixture.directory());
            var received=f.fetch((p,r,k,d)->{
                events.add(r);deadlines.add(d);int attempt=attempts.merge(r.digest(),1,Integer::sum);
                return contact.exchange(p,r,k,d).thenCompose(reply->attempt<3?
                        CompletableFuture.failedFuture(V53LearnerDiscoveryTest.lost()):CompletableFuture.completedFuture(reply));
            });
            assertEquals(f.local.nodeId().value(),received.owned().voter());assertEquals(f.local.storageId(),received.owned().storage());
            assertTrue(attempts.values().stream().allMatch(n->n==3));assertEquals(1,deadlines.size());
            assertEquals(1,events.stream().filter(r->r.kind().equals("TRANSFER_COMMIT")).map(Decoded::digest).distinct().count());
            assertEquals(before,V53ReplayFilesTest.files(f.fixture.directory()));assertEquals(0,endpoint.usage().exports());
            assertThrows(IllegalArgumentException.class,()->f.listen(MembershipTransport.Events.NONE));
            endpoint.close();assertTrue(endpoint.closed());f.pending.close();assertEquals(f.baseline,f.fixture.f.local.source.client.usage());
        }
    }
    @Test void wrongReferencesIdentitiesAndCorrelationsCannotCreateTransfers()throws Exception {
        try(var f=new Fixture();var endpoint=f.listen(MembershipTransport.Events.NONE)) {
            var first=f.first();var usage=f.fixture.f.local.source.client.usage();
            for(String mode:List.of("root","view","ballot","sender","recipient","sequence","digest","offset","kind")) {
                var value=new TreeMap<>(first.value());var payload=new TreeMap<>(object(value.get("payload")));String kind="CHUNK";
                switch(mode) {
                    case "root","view" -> value.put(mode,"a".repeat(64));
                    case "ballot" -> value.put("ballot",Map.of("counter",number(f.ballot.get("counter")),"proposer",f.local.nodeId().value(),"incarnation",f.local.storageId().toString()));
                    case "sender","recipient" -> {var identity=new TreeMap<>(object(value.get(mode)));identity.put("storage",UUID.randomUUID().toString());value.put(mode,identity);}
                    case "sequence" -> value.put("sequence",2L);
                    case "digest" -> payload.put("digest","b".repeat(64));
                    case "offset" -> payload.put("offset",1L);
                    case "kind" -> {kind="PUBLISH";payload=new TreeMap<>(Map.of("certificate","c".repeat(64)));}
                }
                value.put("payload",payload);var changed=decode(encode("wire",kind,value),"wire",kind);
                assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,changed),mode);
                assertEquals(0,endpoint.usage().traces());assertEquals(usage,f.fixture.f.local.source.client.usage());
            }
            var foreign=new MembershipIdentity(f.reader.nodeId(),UUID.randomUUID(),f.reader.endpoint());
            assertThrows(IllegalArgumentException.class,()->endpoint.answer(foreign,first));
            assertEquals(0,endpoint.usage().traces());
        }
    }
    @Test void laterValidCampaignCanReadTheSameEndButCannotChangeAnExistingTraceBallot()throws Exception {
        try(var f=new Fixture();var endpoint=f.listen(MembershipTransport.Events.NONE)) {
            var first=f.first();var value=new TreeMap<>(first.value());var later=new TreeMap<>(f.ballot);later.put("counter",number(later.get("counter"))+1);
            value.put("ballot",later);var request=decode(encode("wire","CHUNK",value),"wire","CHUNK");
            var before=V53ReplayFilesTest.files(f.fixture.directory());f.finish(endpoint,request);
            assertEquals(before,V53ReplayFilesTest.files(f.fixture.directory()));
            var second=f.first();endpoint.answer(f.reader,second);var changed=new TreeMap<>(second.value());changed.put("ballot",later);
            assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,decode(encode("wire","CHUNK",changed),"wire","CHUNK")));
            assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,second));
        }
    }
    @Test void sixExportsAndSharedControlCapacityRemainBounded()throws Exception {
        try(var f=new Fixture();var endpoint=f.listen(MembershipTransport.Events.NONE)) {
            var originals=new ArrayList<Decoded>();var baseline=f.fixture.f.local.source.client.usage();
            for(int i=0;i<6;i++){var first=f.first();originals.add(first);assertEquals("SOURCE_OFFER",endpoint.answer(f.reader,first).kind());}
            assertEquals(6,endpoint.usage().exports());
            assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,f.first()));assertEquals(6,endpoint.usage().exports());
            f.finish(endpoint,originals.getFirst());assertEquals(5,endpoint.usage().exports());
            assertEquals("SOURCE_OFFER",endpoint.answer(f.reader,f.first()).kind());assertEquals(6,endpoint.usage().exports());
            var reservations=new ArrayList<MembershipResources.Lease>();var pool=f.fixture.f.local.source.client;
            try {
                while(pool.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0)<MembershipResources.Unit.CONTROL.count)
                    reservations.add(pool.reserve(MembershipResources.Unit.CONTROL,"occupy-"+reservations.size(),1));
                var full=pool.usage();assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,f.first()));assertEquals(full,pool.usage());
            }finally{reservations.forEach(MembershipResources.Lease::close);}
            assertEquals(baseline.metadata(),pool.usage().metadata());assertEquals(baseline.staging(),pool.usage().staging());
            endpoint.close();assertEquals(0,endpoint.usage().exports());f.pending.close();assertEquals(f.baseline,pool.usage());
        }
    }
    @Test void changedOriginalsAndExpiredCompletionCannotReturnCachedSuccess()throws Exception {
        try(var f=new Fixture();var endpoint=f.listen(MembershipTransport.Events.NONE)) {
            var commit=f.finish(endpoint,f.first());var before=V53ReplayFilesTest.files(f.fixture.directory());
            for(Path member:List.of(f.fixture.directory().resolve(MembershipLearnerDisposition.PENDING_ACK),f.fixture.directory().resolve("source/generation.gsr"))) {
                byte[] bytes=Files.readAllBytes(member),changed=bytes.clone();changed[changed.length/2]^=1;Files.write(member,changed);
                assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,commit));Files.write(member,bytes);
                assertEquals("TRANSFER_COMMIT",endpoint.answer(f.reader,commit).kind());
            }
            f.clock.addAndGet(BUDGET);assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,commit));
            assertTrue(endpoint.closed());assertEquals(before,V53ReplayFilesTest.files(f.fixture.directory()));
            f.pending.close();assertEquals(f.baseline,f.fixture.f.local.source.client.usage());
        }
    }
    @Test void ownerCloseAtTheActualWriteBoundaryRevokesACompletedReply()throws Exception {
        try(var f=new Fixture()) {
            var committed=new AtomicInteger();var hit=new AtomicBoolean();
            try(var endpoint=f.listen((event,request,response)->{
                if(event.equals("BEFORE_RESPONSE_WRITE") && request.kind().equals("TRANSFER_COMMIT") && committed.incrementAndGet()==2) {
                    hit.set(true);f.pending.close();
                }
            });var contact=f.contact()) {
                var requests=new ArrayList<Decoded>();f.fetch((p,r,k,d)->{requests.add(r);return contact.exchange(p,r,k,d);});
                var commit=requests.getLast();assertEquals("TRANSFER_COMMIT",commit.kind());
                assertThrows(ExecutionException.class,()->contact.exchange(f.local,commit,"TRANSFER_COMMIT",System.nanoTime()+BUDGET).get(15,TimeUnit.SECONDS));
                assertTrue(hit.get());assertTrue(endpoint.closed());assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,commit));
                long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(10);
                while(!f.baseline.equals(f.fixture.f.local.source.client.usage())) {assertTrue(System.nanoTime()<until,"closed pending transport drain");Thread.sleep(10);}
            }
        }
    }
    @Test void failedAckForceCannotOpenAnEndpointAndStoreCloseDrainsItsChild()throws Exception {
        var hit=new AtomicBoolean();
        try(var f=new Fixture(event->{if(event.equals("LEARNER_JOINING_ACK_FORCED")){hit.set(true);throw new IOException("force interrupted");}})) {
            var usage=f.fixture.f.local.source.client.usage();assertThrows(IOException.class,()->f.listen(MembershipTransport.Events.NONE));
            assertTrue(hit.get());assertEquals(usage,f.fixture.f.local.source.client.usage());
            try(var probe=new ServerSocket()){probe.bind(new InetSocketAddress(f.local.endpoint().host(),f.local.endpoint().port()));}
        }
        try(var f=new Fixture();var endpoint=f.listen(MembershipTransport.Events.NONE)) {
            var first=f.first();endpoint.answer(f.reader,first);f.fixture.f.local.store.close();
            assertTrue(endpoint.closed());assertEquals(0,endpoint.usage().exports());assertThrows(IllegalArgumentException.class,()->endpoint.answer(f.reader,first));
        }
    }
}
