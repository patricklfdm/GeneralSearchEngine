package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.net.*;
import java.nio.channels.ServerSocketChannel;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real constructor failures and original-resource continuity. Learner/source
 * authority is conditional; this is not whole native joining qualification. */
class V53ConstructionRollbackTest {
    @TempDir Path temp;
    @FunctionalInterface interface Factory {AutoCloseable open()throws Exception;}
    static final class Evidence {
        final Path root;final MembershipResources resources;final String scope;
        final List<Map<String,Object>> cases=new ArrayList<>();
        Evidence(String scope,MembershipResources resources)throws IOException {
            this.scope=scope;this.resources=resources;
            root=Boolean.getBoolean("v53.resource.learner.control.close")?
                    Files.createDirectories(Path.of("target/v53-construction-rollback/run-"+UUID.randomUUID())):null;
            if(root!=null)System.out.println("v53ConstructionRollback="+root.toAbsolutePath()+" scope="+scope);
        }
        Map<String,Object> point() {
            if(root==null)return Map.of();var p=resources.observationCheckpoint();assertTrue(p.complete());
            return Map.of("sequence",p.sequence(),"usage",V53ResourceTraceFiles.usage(p.usage()));
        }
        void failure(String name,Class<? extends Exception> type,Factory factory,Path originals)throws Exception {
            var files=V53PendingListenerDrainTest.inventory(originals);var before=resources.usage();var begin=point();
            Exception error=assertThrows(type,()->{try(var unexpected=factory.open()){fail("constructor unexpectedly succeeded");}});
            var end=point();var after=V53PendingListenerDrainTest.inventory(originals);
            if(root!=null)cases.add(Map.of("case",name,"begin",begin,"failed",end,"error",error.getClass().getName(),
                    "message",String.valueOf(error.getMessage()),"beforeFiles",files,"afterFiles",after));
            assertEquals(before,resources.usage());assertEquals(files,after);
        }
        void finish(Throwable failure)throws Exception {
            if(root==null)return;
            V53ResourceTraceFiles.write(root.resolve("resources.json"),resources.observations());
            Files.write(root.resolve("history.json"),canonical(Map.of("schema","gse-v53-construction-rollback-v1","scope",scope,
                    "status",failure==null?"PASS":"FAIL","cases",cases,"completeMembershipHistory",false),4*1024*1024));
            assertEquals(0,resources.usage().leases());
        }
    }
    static List<MembershipResources.Lease> pressure(MembershipResources resources) {
        var leases=new ArrayList<MembershipResources.Lease>();
        while(resources.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0)<MembershipResources.Unit.CONTROL.count)
            leases.add(resources.reserve(MembershipResources.Unit.CONTROL,"constructor-pressure-"+leases.size(),1));
        return leases;
    }
    static AutoCloseable listener(V53LearnerCheckpointEndpointTest.Fixture f,String name,MembershipLearnerDisposition.RetainedSource retained)throws Exception {
        return name.equals("checkpoint")?f.listen(MembershipTransport.Events.NONE):retained.listenHead(f.fixture.f.local.config.bounds(),MembershipTransport.Events.NONE);
    }
    static void healthy(V53LearnerCheckpointEndpointTest.Fixture f,String name,MembershipLearnerDisposition.RetainedSource retained)throws Exception {
        var before=f.fixture.f.local.source.client.usage();
        try(var endpoint=listener(f,name,retained);var contact=f.contact()) {
            var request=name.equals("checkpoint")?f.first():V53LearnerHeadProtocolTest.query(f.fixture.f.head,f.reader);
            String kind=name.equals("checkpoint")?"SOURCE_OFFER":"LEARNER_HEAD_ACK";
            var reply=contact.exchange(f.local,request,kind,System.nanoTime()+TimeUnit.SECONDS.toNanos(10)).get(15,TimeUnit.SECONDS);
            MembershipWire.correlated(request,reply,kind);
            if(name.equals("checkpoint"))assertEquals(f.expected().digest(),object(reply.value().get("payload")).get("digest"));
        }
        assertEquals(before,f.fixture.f.local.source.client.usage());f.pending.source();
    }
    @ParameterizedTest @ValueSource(strings={"checkpoint","head"})
    void failedListenerConstructionRollsBackAndTheSameOwnerCanServe(String name)throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;Evidence evidence=null;Throwable failure=null;
        try(var f=helper.new Fixture()) {
            f.pending.endorse();var retained=name.equals("head")?f.pending.retainSource():null;
            var resources=f.fixture.f.local.source.client;evidence=new Evidence(name,resources);
            try(var occupied=ServerSocketChannel.open()) {
                occupied.bind(new InetSocketAddress(f.local.endpoint().host(),f.local.endpoint().port()));
                evidence.failure(name+"-bind",BindException.class,()->listener(f,name,retained),f.fixture.directory());
                assertTrue(occupied.isOpen());f.pending.source();
            }
            healthy(f,name,retained);
            var pressure=pressure(resources);
            try{evidence.failure(name+"-capacity",IllegalArgumentException.class,()->listener(f,name,retained),f.fixture.directory());}
            finally{pressure.forEach(MembershipResources.Lease::close);}
            healthy(f,name,retained);
        }catch(Throwable error){failure=error;throw error;}
        finally{if(evidence!=null)evidence.finish(failure);}
    }
    @Test void sourceServiceGuardCapacityAndPostReservationExpiryPreserveTheOriginalOwner()throws Exception {
        var helper=new V53RecordExchangeTest();helper.temp=temp;Evidence evidence=null;Throwable failure=null;
        var resources=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,MembershipResources.QUEUE_LIMIT,
                MembershipResourceObservations.MAXIMUM);
        try(var f=helper.new Local()) {
            evidence=new Evidence("source-service",resources);var ballot=object(f.source.basis.value().get("ballot"));
            Path originals=f.fixture.request.targets().getFirst().replicaDirectory();var bounds=V53TransferServiceTest.bound(2);
            evidence.failure("service-guard",IOException.class,()->new MembershipTransferService(f.owner,ballot,resources,bounds,
                    ()->{throw new IOException("construction guard rejected");},()->0L,0,100),originals);
            var clockCalls=new AtomicInteger();
            evidence.failure("service-expiry",IllegalArgumentException.class,()->new MembershipTransferService(f.owner,ballot,resources,bounds,
                    ()->{},()->clockCalls.getAndIncrement()==0?0L:100L,0,100),originals);assertEquals(2,clockCalls.get());
            var pressure=pressure(resources);
            try{evidence.failure("service-capacity",IllegalArgumentException.class,()->new MembershipTransferService(f.owner,ballot,resources,bounds,()->{},()->0L,0,100),originals);}
            finally{pressure.forEach(MembershipResources.Lease::close);}
            var ownerUsage=f.fixture.resources.usage();var promise=f.owner.promised().orElseThrow();var reader=f.fixture.request.targets().get(1).identity();
            try(var service=new MembershipTransferService(f.owner,ballot,resources,bounds,()->{},()->0L,0,100)) {
                var request=MembershipActivation.frame("CHUNK",f.source.capsule.context,reader,f.owner.activationIdentity(),ballot,UUID.randomUUID(),1,
                        Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest",promise.digest(),"bytes",""));
                var reply=service.handle(reader,request);assertEquals("SOURCE_OFFER",reply.kind());assertEquals(promise.digest(),object(reply.value().get("payload")).get("digest"));
            }
            assertEquals(ownerUsage,f.fixture.resources.usage());assertEquals(0,resources.usage().leases());
        }catch(Throwable error){failure=error;throw error;}
        finally{if(evidence!=null)evidence.finish(failure);}
    }
}
