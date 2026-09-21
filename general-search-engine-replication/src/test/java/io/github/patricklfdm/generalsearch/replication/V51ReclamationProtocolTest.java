package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;
import static io.github.patricklfdm.generalsearch.replication.V51StorageFixture.*;
import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.api.io.TempDir;

/** A retained generation can delay selection adoption without poisoning its voter. */
class V51ReclamationProtocolTest {
    @TempDir Path root;

    private AutomaticStore open(byte[] manifest,int node) {
        return AutomaticStore.open(root.resolve("node-"+node),manifest,"node-"+node,
                ReplicationBounds.defaults(),AutomaticStore.Faults.NONE);
    }
    private Map<Path,byte[]> generations(int node) throws Exception {
        Path directory=root.resolve("node-"+node);var result=new LinkedHashMap<Path,byte[]>();
        result.put(directory.resolve("current.gsr"),Files.readAllBytes(directory.resolve("current.gsr")));
        for(String generation:List.of("generation-a","generation-b"))
            for(String file:AutomaticRecoveryFiles.GENERATION_FILES) {
                Path path=directory.resolve(generation).resolve(file);result.put(path,Files.readAllBytes(path));
            }
        return result;
    }
    @ParameterizedTest @ValueSource(ints={1,2})
    void laggingCandidateOrInstallRecipientWaitsForTwoSourceRetirement(int lagging) throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            for(int i=1;i<=3;i++)group.stop(i);
            byte[] application=unbase(decode(Files.readAllBytes(root.resolve("node-1/genesis.gsr")),"GENESIS").value().get("application"));
            byte[] first=entry(group.manifest,1,null,9,new byte[0]);
            byte[] second=entry(group.manifest,2,first,9,new byte[0]);
            for(int i=1;i<=3;i++)try(var store=open(group.manifest,i)) {
                if(i==lagging)store.checkpoint(application);
                store.promise(promise(group.manifest,2));
                store.accept(accept(group.manifest,first,2));store.prove(proof(group.manifest,first,2));
                store.checkpoint(application);
                if(i!=lagging) {store.accept(accept(group.manifest,second,2));store.prove(proof(group.manifest,second,2));}
            }
            var before=generations(lagging);
            group.open(1,AutomaticStore.Faults.NONE);group.open(2,AutomaticStore.Faults.NONE);group.pump();
            group.elect(1);
            assertNotEquals(FAILED,group.node(lagging).view().state());
            assertNotEquals(LEADER_READY,group.node(1).view().state());
            assertEquals(1,group.node(lagging).view().provenIndex());
            for(var file:before.entrySet())assertArrayEquals(file.getValue(),Files.readAllBytes(file.getKey()));
            assertFalse(Files.exists(root.resolve("node-"+lagging+"/recovery-floor.gsr")));
            if(lagging==2)assertTrue(group.messages.stream().anyMatch(m->m.response()
                    &&m.kind()==AutomaticProtocol.Kind.INSTALL&&!m.accepted()
                    &&m.payload()==AutomaticReplicationException.Reason.CAPACITY_EXCEEDED));
            long epoch=group.node(lagging).view().promisedEpoch();
            group.stop(1);group.stop(2);
            try(var local=open(group.manifest,lagging);var peer=open(group.manifest,3)) {
                assertFalse(local.quarantined());assertEquals(epoch,number(local.promised().value(),"epoch"));
                local.establishRecoveryFloor(List.of(local.recoverySource(),peer.recoverySource()));local.cleanup();
            }
            group.open(1,AutomaticStore.Faults.NONE);group.open(2,AutomaticStore.Faults.NONE);group.pump();
            group.elect(1);
            assertEquals(LEADER_READY,group.node(1).view().state());
            assertEquals(3,group.node(1).view().publishedIndex());
            var snapshot=decode(unbase(group.publications.getLast().get("snapshot")),"SNAPSHOT");
            assertEquals(digest(second),object(list(snapshot.value().get("anchors")).get(1)).get("entryDigest"));
        }
    }
}
