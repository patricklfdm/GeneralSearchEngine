package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import static org.junit.jupiter.api.Assertions.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.Callable;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Deterministic maintenance exchanges over real stores, without election or wall-clock races. */
class V51RejoinCompletionTest {
    @TempDir Path root;
    private final class Pair implements AutoCloseable {
        final byte[] manifest=setup(root);
        Record ballot=decode(V51StorageFixture.promise(manifest,2),"PROMISE");
        final AutomaticStore[] stores=new AutomaticStore[2];
        final AutomaticProtocol[] protocols=new AutomaticProtocol[2];
        final AutomaticRejoin[] exchanges=new AutomaticRejoin[2];
        final AtomicLong ids=new AtomicLong();
        final List<String> requests=new ArrayList<>();
        int installed;boolean loseAck,badAck,failProbe;Long reportedIndex;
        final AutomaticRejoin.Control control=new AutomaticRejoin.Control() {
            public <R> R call(Callable<R> task)throws Exception{return task.call();}
        };
        Pair() throws Exception {
            for(int i=0;i<2;i++) {
                String node="node-"+(i+1);
                stores[i]=AutomaticStore.open(root.resolve(node),manifest,node,ReplicationBounds.defaults(),AutomaticStore.Faults.NONE);
                stores[i].promise(ballot.bytes());
                protocols[i]=new AutomaticProtocol(stores[i],()->0L,UUID::randomUUID);
                byte[] application=unbase(decode(Files.readAllBytes(root.resolve(node+"/genesis.gsr")),"GENESIS").value().get("application"));
                protocols[i].restored(application);protocols[i].start(0);protocols[i].drain();
                stores[i].checkpoint(application);
            }
            exchanges[1]=new AutomaticRejoin(stores[1],protocols[1],control,r->{throw new AssertionError("unexpected sender");},()->0L,ids::incrementAndGet,
                (event,values)->{if(event.equals("REJOIN_INSTALLED"))installed++;});
            exchanges[0]=sender();
        }
        void promise(int i,Record value) {
            protocols[i].receive(new AutomaticProtocol.Message(ids.incrementAndGet(),AutomaticProtocol.Kind.PREPARE,
                "node-1","node-"+(i+1),value,false,true,null,null),0);
            reconstruct(i,0);
        }
        void reconstruct(int i,long now) {
            for(var action:protocols[i].drain())if(action instanceof AutomaticProtocol.Reconstruct r)
                protocols[i].reconstructed(r.id(),V51ProtocolFixture.project(r.replay()),null,now);
            protocols[i].drain();
        }
        AutomaticRejoin sender() {
            return new AutomaticRejoin(stores[0],protocols[0],control,request->{
                String type=text(request,"type");requests.add(type);
                if(type.equals("AUTHORITY_STATUS_PROBE")&&failProbe)throw new IOException("status unavailable");
                var response=exchanges[1].handle(request);
                if(type.equals("AUTHORITY_STATUS_PROBE")&&reportedIndex!=null) {
                    var payload=new LinkedHashMap<>(object(response.get("payload")));
                    payload.put("provenIndex",reportedIndex);
                    return AutomaticWire.reply(request,"AUTHORITY_STATUS",payload);
                }
                if(type.equals("REJOIN_INSTALL")&&loseAck) {loseAck=false;throw new IOException("lost install ACK");}
                if(type.equals("REJOIN_INSTALL")&&badAck) {
                    badAck=false;var payload=new LinkedHashMap<>(object(response.get("payload")));payload.put("transferId",UUID.randomUUID().toString());
                    return AutomaticWire.reply(request,type,payload);
                }
                return response;
            },()->0L,ids::incrementAndGet,AutomaticRuntime.Events.NONE);
        }
        void catchup(Record snapshot) throws Exception {
            Class<?> cut=Class.forName(AutomaticRejoin.class.getName()+"$Cut");
            var constructor=cut.getDeclaredConstructor(Record.class,Record.class);constructor.setAccessible(true);
            var method=AutomaticRejoin.class.getDeclaredMethod("catchup",cut,String.class);method.setAccessible(true);
            try {method.invoke(exchanges[0],constructor.newInstance(ballot,snapshot),"node-2");}
            catch(java.lang.reflect.InvocationTargetException error) {
                if(error.getCause() instanceof Exception cause)throw cause;throw (Error)error.getCause();
            }
        }
        Record snapshot(){return stores[0].currentSource().snapshot();}
        Record advance() {
            byte[] entry=entry(manifest,1,null,9,new byte[0]);
            stores[0].accept(accept(manifest,entry,2));stores[0].prove(proof(manifest,entry,2));
            return stores[0].provenSnapshot(unbase(snapshot().value().get("application")));
        }
        long offers(){return requests.stream().filter("SNAPSHOT_OFFER"::equals).count();}
        @Override public void close()throws Exception {
            for(var exchange:exchanges){exchange.stop();exchange.close();}
            for(var protocol:protocols)protocol.close();
        }
    }
    @Test void confirmedSameSnapshotIsNotTransferredAgainButEveryCycleStillProbes() throws Exception {
        try(var p=new Pair()) {
            var snapshot=p.snapshot();p.catchup(snapshot);
            // Native failure 38033332912 installed one identical snapshot 87 times.
            for(int i=0;i<100;i++)p.catchup(snapshot);
            assertEquals(1,p.installed);assertEquals(1,p.offers());
            assertEquals(101,p.requests.stream().filter("AUTHORITY_STATUS_PROBE"::equals).count());
            assertArrayEquals(snapshot.bytes(),p.stores[1].currentSource().snapshot().bytes());
        }
    }
    @Test void unconfirmedOrMalformedInstallResponseNeverSuppressesRecovery() throws Exception {
        try(var p=new Pair()) {
            var snapshot=p.snapshot();p.loseAck=true;assertThrows(IOException.class,()->p.catchup(snapshot));
            p.badAck=true;assertThrows(AutomaticReplicationException.class,()->p.catchup(snapshot));
            p.catchup(snapshot);p.catchup(snapshot);
            assertEquals(3,p.installed);assertEquals(3,p.offers());
        }
    }
    @Test void alteredSameIndexSnapshotCannotReuseConfirmationOrBypassIntegrity() throws Exception {
        try(var p=new Pair()) {
            var first=p.snapshot();p.catchup(first);
            // Equal proven indexes alone do not prove that the application snapshot was installed.
            var value=new LinkedHashMap<>(first.value());value.put("application",b64(new byte[]{1,2,3}));
            var second=decode(encode("SNAPSHOT",value),"SNAPSHOT");
            assertThrows(AutomaticReplicationException.class,()->p.catchup(second));
            assertEquals(2,p.offers());assertEquals(1,p.installed);
        }
    }
    @Test void higherPromiseStillFencesEvenAfterConfirmedInstall() throws Exception {
        try(var p=new Pair()) {
            p.catchup(p.snapshot());var higher=decode(promise(p.manifest,5),"PROMISE");
            p.promise(1,higher);p.catchup(p.snapshot());
            assertFalse(p.protocols[0].maintenanceCurrent(p.ballot));assertEquals(1,p.offers());
        }
    }
    @Test void peerRegressionAndChangedBallotCannotReusePriorCompletion() throws Exception {
        try(var p=new Pair()) {
            p.catchup(p.snapshot());var snapshot=p.advance();p.catchup(snapshot);
            p.reportedIndex=0L;p.catchup(snapshot);p.reportedIndex=null;
            assertEquals(3,p.offers());
            p.protocols[0].tick(20000);p.reconstruct(0,20000);p.ballot=p.protocols[0].promise();p.promise(1,p.ballot);
            p.catchup(snapshot);p.catchup(snapshot);assertEquals(4,p.offers());
        }
    }
    @Test void failedProbeAndFreshControllerDoNotTrustOldCompletion() throws Exception {
        try(var p=new Pair()) {
            var snapshot=p.snapshot();p.catchup(snapshot);p.failProbe=true;
            assertThrows(IOException.class,()->p.catchup(snapshot));p.failProbe=false;
            p.exchanges[0].stop();p.exchanges[0].close();p.exchanges[0]=p.sender();
            // A new sender uses a new wire trace. The old receiver correctly
            // refuses that offer in the same ballot; a fresh controller must
            // attempt recovery rather than inherit the old in-memory success.
            assertThrows(AutomaticReplicationException.class,()->p.catchup(snapshot));assertEquals(2,p.offers());
        }
    }
}
