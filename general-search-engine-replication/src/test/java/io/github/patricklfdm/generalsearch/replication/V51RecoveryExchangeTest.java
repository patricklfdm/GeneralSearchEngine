package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import static org.junit.jupiter.api.Assertions.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.Callable;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51RecoveryExchangeTest {
    @TempDir Path root;
    private final class Fixture implements AutoCloseable {
        final byte[] manifest=setup(root);final Record m=decode(manifest,"MANIFEST"),ballot=decode(promise(manifest,2),"PROMISE");
        final AutomaticStore store=AutomaticStore.open(root.resolve("node-2"),manifest,"node-2",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE);
        final AutomaticProtocol protocol=new AutomaticProtocol(store,()->0L,UUID::randomUUID);
        final AtomicLong time=new AtomicLong(),ids=new AtomicLong();
        final UUID trace=UUID.randomUUID();
        final AutomaticRejoin exchange;
        Fixture() throws Exception {
            byte[] application=unbase(decode(Files.readAllBytes(root.resolve("node-2/genesis.gsr")),"GENESIS").value().get("application"));
            protocol.start(0);var action=(AutomaticProtocol.Reconstruct)protocol.drain().getFirst();protocol.reconstructed(action.id(),application,null,0);
            protocol.receive(new AutomaticProtocol.Message(1,AutomaticProtocol.Kind.PREPARE,"node-1","node-2",ballot,false,true,null,null),0);protocol.drain();
            store.checkpoint(application);
            exchange=new AutomaticRejoin(store,protocol,new AutomaticRejoin.Control(){public <R> R call(Callable<R> action)throws Exception{return action.call();}},r->{throw new AssertionError("unexpected network");},time::get,ids::incrementAndGet,AutomaticRuntime.Events.NONE);
        }
        Map<String,Object> call(String type,Map<String,Object> payload) throws Exception {
            return exchange.handle(AutomaticWire.message(m,ballot,"node-1","node-2",type,trace,ids.incrementAndGet(),payload));
        }
        Map<String,Object> offer(String id) {return Map.of("transferId",id,"response",false,"index",0L,"sourceBytes",0L,"sourceDigest",sha(new byte[0]));}
        @Override public void close() throws Exception {exchange.stop();exchange.close();protocol.close();}
    }
    @Test void sourceRetryIsImmutableAndOriginalLifetimeCannotBeExtended() throws Exception {
        try(var f=new Fixture()) {
            String id=UUID.randomUUID().toString();var first=f.call("SOURCE_OFFER",f.offer(id));String lease=text(object(first.get("payload")),"transferId");
            long life=f.store.leadershipPolicy().operationTimeoutMillis();f.time.set(life-1);
            assertEquals(first.get("payload"),f.call("SOURCE_OFFER",f.offer(id)).get("payload"));
            f.time.set(life);
            assertThrows(Exception.class,()->f.call("SOURCE_CHUNK",Map.of("transferId",lease,"action","REQUEST","offset",0L,"maxChunkBytes",4096L,"chunkBytes",0L,"chunk","","chunkDigest",sha(new byte[0]))));
            assertNotEquals(lease,object(f.call("SOURCE_OFFER",f.offer(id)).get("payload")).get("transferId"));
            assertFalse(f.store.quarantined());
        }
    }
    @Test void liveLeasePressureRejectsNewIdentityAndHigherPromiseRetiresOldSource() throws Exception {
        try(var f=new Fixture()) {
            f.call("SOURCE_OFFER",f.offer(UUID.randomUUID().toString()));
            assertThrows(Exception.class,()->f.call("SOURCE_OFFER",f.offer(UUID.randomUUID().toString())));assertFalse(f.store.quarantined());
            var higher=decode(promise(f.manifest,5),"PROMISE");f.protocol.receive(new AutomaticProtocol.Message(2,AutomaticProtocol.Kind.PREPARE,"node-1","node-2",higher,false,true,null,null),0);f.protocol.drain();
            assertThrows(Exception.class,()->f.call("SOURCE_OFFER",f.offer(UUID.randomUUID().toString())));assertEquals(5L,f.store.promised().value().get("epoch"));
        }
    }
    @Test void transferChunkRetryIsExactAndExpiryCannotInstallStagedBytes() throws Exception {
        try(var f=new Fixture()) {
            var snapshot=f.store.currentSource().snapshot();byte[] image=AutomaticRecovery.image(f.m,snapshot,null);String id=UUID.randomUUID().toString();
            f.call("SNAPSHOT_OFFER",Map.of("transferId",id,"imageBytes",(long)image.length,"imageDigest",digest(image),"response",false));
            var data=Map.<String,Object>of("transferId",id,"action","DATA","offset",0L,"maxChunkBytes",4096L,"chunkBytes",(long)image.length,"chunk",b64(image),"chunkDigest",sha(image));
            assertEquals(f.call("SNAPSHOT_CHUNK",data).get("payload"),f.call("SNAPSHOT_CHUNK",data).get("payload"));
            f.time.set(f.store.leadershipPolicy().operationTimeoutMillis());
            assertThrows(Exception.class,()->f.call("SNAPSHOT_OFFER",Map.of("transferId",id,"imageBytes",(long)image.length,"imageDigest",digest(image),"response",false)));
            assertThrows(Exception.class,()->f.call("REJOIN_INSTALL",Map.of("transferId",id,"imageDigest",digest(image),"response",false)));
            assertFalse(f.store.quarantined());assertEquals(0,f.store.status().get("provenThrough"));
        }
    }
    @Test void sourcePacketRejectsMissingDuplicateAndChangedGenerationFiles() throws Exception {
        try(var f=new Fixture()) {
            var packet=AutomaticRejoin.packetValue(f.store.recoverySource());assertEquals("node-2",AutomaticRejoin.packet(canonical(packet),f.m).seal().value().get("node"));
            var rows=new ArrayList<>(list(packet.get("files")));rows.removeLast();assertThrows(AutomaticReplicationException.class,()->AutomaticRejoin.packet(canonical(Map.of("files",rows)),f.m));
            rows.add(rows.getFirst());assertThrows(AutomaticReplicationException.class,()->AutomaticRejoin.packet(canonical(Map.of("files",rows)),f.m));
        }
    }
}
