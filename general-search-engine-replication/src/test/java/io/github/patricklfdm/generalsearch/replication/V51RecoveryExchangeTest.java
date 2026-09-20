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
    private static Map<String,Object> data(String id,int offset,byte[] bytes) {
        return Map.of("transferId",id,"action","DATA","offset",(long)offset,"maxChunkBytes",4096L,"chunkBytes",(long)bytes.length,"chunk",b64(bytes),"chunkDigest",sha(bytes));
    }
    private Map<String,Object> seedOffer(String nonce,AutomaticRecoveryFiles.Source source) {
        byte[] bytes=canonical(AutomaticRejoin.packetValue(source));
        return Map.of("transferId",nonce,"response",false,"index",(long)AutomaticRecovery.index(source.snapshot()),"sourceBytes",(long)bytes.length,"sourceDigest",sha(bytes));
    }
    private AutomaticRecoveryFiles.Source seedAndDownload(Fixture f,AutomaticRecoveryFiles.Source own) throws Exception {
        String nonce=UUID.randomUUID().toString();byte[] bytes=canonical(AutomaticRejoin.packetValue(own));
        String upload=text(object(f.call("SOURCE_OFFER",seedOffer(nonce,own)).get("payload")),"transferId");
        for(int offset=0;offset<bytes.length;offset+=4096) {
            var chunk=data(upload,offset,Arrays.copyOfRange(bytes,offset,Math.min(bytes.length,offset+4096)));
            assertEquals(f.call("SOURCE_CHUNK",chunk).get("payload"),f.call("SOURCE_CHUNK",chunk).get("payload"));
        }
        var query=new LinkedHashMap<>(f.offer(nonce));query.put("index",(long)AutomaticRecovery.index(own.snapshot()));
        var offered=object(f.call("SOURCE_OFFER",query).get("payload"));String export=text(offered,"transferId");assertNotEquals(upload,export);
        var downloaded=new java.io.ByteArrayOutputStream();
        while(downloaded.size()<number(offered,"sourceBytes")) {
            var chunk=Map.<String,Object>of("transferId",export,"action","REQUEST","offset",(long)downloaded.size(),"maxChunkBytes",4096L,"chunkBytes",0L,"chunk","","chunkDigest",sha(new byte[0]));
            downloaded.write(unbase(object(f.call("SOURCE_CHUNK",chunk).get("payload")).get("chunk")));
        }
        assertEquals(offered.get("sourceDigest"),sha(downloaded.toByteArray()));return AutomaticRejoin.packet(downloaded.toByteArray(),f.m);
    }
    @Test void differentFullGenerationCutsConvergeWithoutRollingBackHigherPeer() throws Exception {
        try(var f=new Fixture();var a=AutomaticStore.open(root.resolve("node-1"),f.manifest,"node-1",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE)) {
            a.checkpoint(unbase(decode(Files.readAllBytes(root.resolve("node-1/genesis.gsr")),"GENESIS").value().get("application")));
            byte[] first=entry(f.manifest,1,null,1,new byte[]{1}),second=entry(f.manifest,2,first,1,new byte[]{2});
            a.promise(f.ballot.bytes());
            for(var s:List.of(a,f.store)){s.accept(accept(f.manifest,first,2));s.prove(proof(f.manifest,first,2));}
            a.checkpoint(new byte[]{1});
            for(var s:List.of(a,f.store)){s.accept(accept(f.manifest,second,2));s.prove(proof(f.manifest,second,2));}
            f.store.checkpoint(new byte[]{2});
            byte[] tail=entry(f.manifest,3,second,1,new byte[]{3});f.store.accept(accept(f.manifest,tail,2));
            var own=a.recoverySource();var higher=f.store.recoverySource();
            assertFalse(a.generationAvailable(a.provenSnapshot(new byte[]{2})));
            var query=new LinkedHashMap<>(f.offer(UUID.randomUUID().toString()));query.put("index",1L);
            assertEquals(AutomaticReplicationException.Reason.NOT_READY,assertThrows(AutomaticReplicationException.class,()->f.call("SOURCE_OFFER",query)).reason());
            var remote=seedAndDownload(f,own);
            assertEquals("node-2",remote.seal().value().get("node"));assertEquals(1,AutomaticRecovery.index(remote.snapshot()));
            assertEquals(higher.seal().digest(),f.store.currentSource().seal().digest());assertEquals(2,f.store.status().get("provenThrough"));
            assertArrayEquals(tail,f.store.acceptedEntry(3));
            a.establishRecoveryFloor(List.of(own,remote));a.cleanup();assertTrue(a.generationAvailable(a.provenSnapshot(new byte[]{2})));
            a.installProven(a.provenSnapshot(new byte[]{2}));a.establishRecoveryFloor(List.of(a.recoverySource(),higher));a.cleanup();
            f.store.establishRecoveryFloor(List.of(f.store.recoverySource(),a.recoverySource()));f.store.cleanup();
            assertFalse(a.quarantined());assertFalse(f.store.quarantined());
        }
        var manifest=Files.readAllBytes(root.resolve("node-2/manifest.gsr"));
        try(var s=AutomaticStore.open(root.resolve("node-2"),manifest,"node-2",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE)) {
            assertEquals(2,s.status().get("provenThrough"));assertEquals(2,AutomaticRecovery.index(s.currentSource().snapshot()));
            assertEquals(3,s.status().get("acceptedThrough"));
        }
    }
    @Test void sourceSeedRejectsChangedBytesAndExpiresWithoutCreatingAuthority() throws Exception {
        try(var f=new Fixture();var a=AutomaticStore.open(root.resolve("node-1"),f.manifest,"node-1",ReplicationBounds.defaults(),AutomaticStore.Faults.NONE)) {
            a.checkpoint(unbase(decode(Files.readAllBytes(root.resolve("node-1/genesis.gsr")),"GENESIS").value().get("application")));
            var own=a.recoverySource();String nonce=UUID.randomUUID().toString();var offered=seedOffer(nonce,own);
            var before=f.store.currentSource().seal().digest();String id=text(object(f.call("SOURCE_OFFER",offered).get("payload")),"transferId");
            byte[] bytes=Arrays.copyOf(canonical(AutomaticRejoin.packetValue(own)),32);f.call("SOURCE_CHUNK",data(id,0,bytes));
            bytes[0]^=1;assertThrows(AutomaticReplicationException.class,()->f.call("SOURCE_CHUNK",data(id,0,bytes)));
            assertThrows(AutomaticReplicationException.class,()->f.call("SOURCE_OFFER",f.offer(UUID.randomUUID().toString())));
            f.time.set(f.store.leadershipPolicy().operationTimeoutMillis());
            assertThrows(AutomaticReplicationException.class,()->f.call("SOURCE_OFFER",offered));
            assertThrows(AutomaticReplicationException.class,()->f.call("SOURCE_CHUNK",data(id,0,bytes)));
            assertEquals(before,f.store.currentSource().seal().digest());assertFalse(Files.exists(root.resolve("node-2/transfer/witness")));assertFalse(f.store.quarantined());
        }
    }
}
