package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import static org.junit.jupiter.api.Assertions.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51RecoveryWitnessTest {
    @TempDir Path root;
    @Test void everyWitnessFileInterruptionKeepsActiveAuthorityAndAllowsFreshRetry() throws Exception {
        for(String barrier:List.of("WITNESS_BEFORE_WRITE","WITNESS_AFTER_WRITE","WITNESS_AFTER_FORCE","SOURCE_BEFORE_ACK")) {
            for(int file=1;file<=(barrier.equals("SOURCE_BEFORE_ACK")?1:5);file++) {
                Path path=Files.createDirectory(root.resolve(barrier+file));byte[] manifest=setup(path);String before;
                AutomaticRecoveryFiles.Source source;
                try(var a=open(path,manifest,1,AutomaticStore.Faults.NONE);var b=open(path,manifest,2,AutomaticStore.Faults.NONE)) {
                    byte[] first=entry(manifest,1,null,1,new byte[]{1});
                    for(var store:List.of(a,b)){store.promise(promise(manifest,2));store.accept(accept(manifest,first,2));store.prove(proof(manifest,first,2));store.checkpoint(new byte[]{1});}
                    source=a.recoverySource();before=b.currentSource().seal().digest();
                }
                int selected=file;var occurrences=new AtomicInteger();
                AutomaticStore.Faults faults=new AutomaticStore.Faults(){public void at(String event)throws java.io.IOException {
                    if(event.equals(barrier)&&occurrences.incrementAndGet()==selected)throw new java.io.IOException("witness interruption");
                }};
                try(var b=open(path,manifest,2,faults)) {
                    assertThrows(AutomaticReplicationException.class,()->b.retainWitness("node-1",source.snapshot()));assertTrue(b.quarantined());
                }
                try(var b=open(path,manifest,2,AutomaticStore.Faults.NONE)) {
                    assertEquals(before,b.currentSource().seal().digest());assertEquals(1,b.status().get("provenThrough"));
                    assertEquals("node-2",b.retainWitness("node-1",source.snapshot()).seal().value().get("node"));
                    assertFalse(Files.exists(path.resolve("node-2/recovery-floor.gsr")));
                }
            }
        }
    }
    @Test void witnessCannotIntroduceUnprovenOrConflictingHistory() throws Exception {
        byte[] manifest=setup(root);
        try(var a=open(root,manifest,1,AutomaticStore.Faults.NONE);var b=open(root,manifest,2,AutomaticStore.Faults.NONE)) {
            byte[] first=entry(manifest,1,null,1,new byte[]{1});a.promise(promise(manifest,2));a.accept(accept(manifest,first,2));a.prove(proof(manifest,first,2));a.checkpoint(new byte[]{1});
            var snapshot=a.recoverySource().snapshot();
            assertEquals(AutomaticReplicationException.Reason.NOT_READY,assertThrows(AutomaticReplicationException.class,()->b.retainWitness("node-1",snapshot)).reason());
            assertFalse(b.quarantined());assertFalse(Files.exists(root.resolve("node-2/transfer/witness")));
            byte[] conflicting=entry(manifest,1,null,1,new byte[]{2});b.promise(promise(manifest,2));b.accept(accept(manifest,conflicting,2));b.prove(proof(manifest,conflicting,2));b.checkpoint(new byte[]{2});
            assertThrows(AutomaticReplicationException.class,()->b.retainWitness("node-1",snapshot));
            assertFalse(Files.exists(root.resolve("node-2/transfer/witness")));
        }
    }
    private AutomaticStore open(Path path,byte[] manifest,int node,AutomaticStore.Faults faults) {
        return AutomaticStore.open(path.resolve("node-"+node),manifest,"node-"+node,ReplicationBounds.defaults(),faults);
    }
}
