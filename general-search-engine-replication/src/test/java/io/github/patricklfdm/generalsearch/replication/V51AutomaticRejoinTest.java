package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V51AutomaticRejoinTest {
    @TempDir Path root;
    static void converged(V51RuntimeFixture group,long cut) throws Exception {
        long end=System.nanoTime()+TimeUnit.SECONDS.toNanos(35);
        while(System.nanoTime()<end) {
            boolean ready=true;
            for(var entry:group.nodes.entrySet()) {
                assertNull(entry.getValue().failure());assertNotEquals(AutomaticReplicationState.FAILED,entry.getValue().view().state());
                Path floor=group.root.resolve(entry.getKey()).resolve("recovery-floor.gsr");
                if(!Files.exists(floor)||number(decode(Files.readAllBytes(floor),"FLOOR").value(),"index")<cut)ready=false;
            }
            if(ready)return;Thread.sleep(50);
        }
        fail("rejoin/floor did not converge: "+group.nodes.entrySet().stream().map(e->e.getKey()+":"+e.getValue().view()+" recovery="+e.getValue().lastRecoveryFailure()+" rejected="+e.getValue().lastRecoveryRejection()).toList());
    }
    @Test void repeatedThreeVoterCatchupReclaimsSlotsAndRetainedPeerCanLead() throws Exception {
        try(var group=new V51RuntimeFixture(root)) {
            var leader=group.leader();String first=group.name(leader);
            for(int i=1;i<=4;i++) {
                long cut=leader.submit(1,app->app.documents("ADD",List.of(new Document((int)app.sequence()+1,"large-".repeat(1800))))).get(20,TimeUnit.SECONDS);
                converged(group,cut);
            }
            group.stop(first);leader=group.leader();
            assertEquals(4,leader.inspectLocal(e->e.search(d->true).size()).get(5,TimeUnit.SECONDS));
            group.open(Integer.parseInt(first.substring(5)));assertNotEquals(AutomaticReplicationState.LEADER_READY,group.nodes.get(first).view().state());
            long cut=leader.submit(1,app->app.documents("ADD",List.of(new Document(99,"after-rejoin")))).get(20,TimeUnit.SECONDS);
            converged(group,cut);
            assertTrue(group.wire.stream().anyMatch(w->w.get("type").equals("SOURCE_CHUNK")));
        }
        for(int i=1;i<=3;i++) {
            Path node=root.resolve("node-"+i);var manifest=Files.readAllBytes(node.resolve("manifest.gsr"));
            try(var store=AutomaticStore.open(node,manifest,"node-"+i,V51RuntimeFixture.BOUNDS,AutomaticStore.Faults.NONE)) {
                assertEquals(5L,store.status().get("applicationSequence"));assertNotNull(store.recoverySource());
            }
        }
    }
    @Test void lostInstallResponseAndSourceChunkDisconnectRecoverWithoutChangingAuthority() throws Exception {
        var install=new AtomicBoolean();var source=new AtomicBoolean();
        try(var group=new V51RuntimeFixture(root,true,false)) {
            for(int i=1;i<=3;i++)group.open(i,AutomaticStore.Faults.NONE,AutomaticRuntime.Events.NONE,(barrier,request,response)->{
                if(barrier.equals("BEFORE_RESPONSE_WRITE")&&response.get("type").equals("REJOIN_INSTALL")&&install.compareAndSet(false,true))throw new java.io.IOException("lost install ACK");
                if(barrier.equals("BEFORE_RESPONSE_WRITE")&&response.get("type").equals("SOURCE_CHUNK")&&source.compareAndSet(false,true))throw new java.io.IOException("source disconnect");
            });
            var leader=group.leader();long cut=leader.submit(1,app->app.documents("ADD",List.of(new Document(1,"retained")))).get(20,TimeUnit.SECONDS);
            converged(group,cut);assertTrue(install.get());assertTrue(source.get());
            assertEquals("retained",leader.inspectLocal(e->e.get(1).value()).get(5,TimeUnit.SECONDS));
        }
    }
    @Test void threeDifferentFullGenerationCutsRecoverOverRealTcp() throws Exception {
        var witnesses=new java.util.concurrent.atomic.AtomicInteger();
        try(var group=new V51RuntimeFixture(root,true,false)) {
            // Every voter proves the same prefix, but checkpoints at a different cut with both slots occupied.
            // Without exact-cut witness exchange no pair can establish a floor or install the next generation.
            for(int node=1;node<=3;node++)try(var store=AutomaticStore.open(root.resolve("node-"+node),group.manifest,"node-"+node,V51RuntimeFixture.BOUNDS,AutomaticStore.Faults.NONE)) {
                byte[] application=unbase(decode(Files.readAllBytes(root.resolve("node-"+node+"/genesis.gsr")),"GENESIS").value().get("application"));
                store.checkpoint(application);store.promise(V51StorageFixture.promise(group.manifest,2));byte[] previous=null;
                for(int index=1;index<=3;index++) {
                    byte[] entry=V51StorageFixture.entry(group.manifest,index,previous,9,new byte[0]);
                    store.accept(V51StorageFixture.accept(group.manifest,entry,2));store.prove(V51StorageFixture.proof(group.manifest,entry,2));
                    if(index==node)store.checkpoint(application);previous=entry;
                }
                assertTrue(Files.isDirectory(root.resolve("node-"+node+"/generation-a")));assertTrue(Files.isDirectory(root.resolve("node-"+node+"/generation-b")));
            }
            for(int node=1;node<=3;node++)group.open(node,AutomaticStore.Faults.NONE,(event,values)->{
                if(event.equals("SOURCE_WITNESS"))witnesses.incrementAndGet();
            },(barrier,request,response)->{});
            var leader=group.leader();converged(group,leader.view().provenIndex());
            assertTrue(witnesses.get()>0);long cut=leader.submit(1,app->app.documents("ADD",List.of(new Document(1,"after-mismatched-cuts")))).get(20,TimeUnit.SECONDS);
            converged(group,cut);assertEquals("after-mismatched-cuts",leader.inspectLocal(e->e.get(1).value()).get(5,TimeUnit.SECONDS));
        }
    }
}
