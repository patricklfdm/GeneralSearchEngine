package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Real selected-source lifetime on the activating owner's pool. No receiver is
 * manufactured or kept across campaigns by a fixture. The only fault is an
 * unexpected file at the local installation cut, before normal receiver drain. */
class V53ActivationReceiveLifetimeTest {
    @TempDir Path temp;
    record Key(MembershipResources.Unit unit,String owner) {}
    record Cut(Map<Key,MembershipResourceObservations.Charge> charges,Map<Path,String> files) {}

    static Map<Key,MembershipResourceObservations.Charge> live(MembershipResources resources) {
        var snapshot=resources.observations();assertFalse(snapshot.failed());assertFalse(snapshot.truncated());
        var result=new HashMap<Key,MembershipResourceObservations.Charge>();
        for(var row:snapshot.changes()) {
            for(var charge:row.removed())assertEquals(charge,result.remove(new Key(charge.unit(),charge.owner())));
            for(var charge:row.added())assertNull(result.put(new Key(charge.unit(),charge.owner()),charge));
        }
        return result;
    }
    static Map<Path,String> packets(Path scratch)throws IOException {
        var result=new HashMap<Path,String>();
        try(var walk=Files.walk(scratch)) {
            for(var path:walk.filter(p->p.getFileName().toString().equals("source.gscp")).toList()) {
                assertFalse(Files.isSymbolicLink(path));result.put(path,hash(Files.readAllBytes(path)));
            }
        }
        return result;
    }
    static void originalReceiving(Cut cut,Map<String,Map<String,Object>> offers,int count) {
        assertEquals(count,offers.size());assertEquals(count,cut.files.size());
        var expected=new ArrayList<String>();
        offers.forEach((id,offer)->{
            var lease=cut.charges.get(new Key(MembershipResources.Unit.SOURCE,id));assertNotNull(lease,id);
            assertEquals(number(offer.get("bytes")),lease.bytes());assertEquals("",lease.claimSource());
            expected.add((String)offer.get("digest"));
        });
        assertEquals(expected.stream().sorted().toList(),cut.files.values().stream().sorted().toList());
        assertTrue(cut.charges.values().stream().anyMatch(c->c.unit()==MembershipResources.Unit.GENERATION));
        assertTrue(cut.charges.values().stream().anyMatch(c->c.unit()==MembershipResources.Unit.APPLICATION));
        assertTrue(cut.charges.values().stream().anyMatch(c->c.owner().startsWith("received-records-")));
        assertTrue(cut.charges.values().stream().noneMatch(c->c.unit()==MembershipResources.Unit.LEARNER));
    }
    static void drained(V53ActivationDriverTest.Local local,Map<String,Map<String,Object>> offers)throws IOException {
        var state=live(local.budgets.getFirst());
        for(String id:offers.keySet())assertFalse(state.containsKey(new Key(MembershipResources.Unit.SOURCE,id)));
        assertTrue(state.values().stream().noneMatch(c->c.owner().startsWith("received-records-")));
        assertTrue(packets(local.driverScratch).isEmpty());
        // Receiving cleanup must preserve installed authority and its durable originals.
        assertNotNull(local.owners.getFirst().originalSelection().orElseThrow());
        assertTrue(state.values().stream().anyMatch(c->c.unit()==MembershipResources.Unit.GENERATION));
        assertTrue(state.values().stream().anyMatch(c->c.unit()==MembershipResources.Unit.APPLICATION));
    }
    void check(int size,boolean damage)throws Exception {
        var helper=new V53ActivationDriverTest();helper.temp=temp;
        try(var local=helper.new Local(size,false,Files.createDirectory(temp.resolve("raw")),()->0,1000,
                ()->new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                    MembershipResources.QUEUE_LIMIT,MembershipResourceObservations.MAXIMUM));
            var driver=local.driver(1)) {
            var offers=new ConcurrentHashMap<String,Map<String,Object>>();var normal=local.override.get();
            local.override.set((peer,request,kind,deadline)->normal.exchange(peer,request,kind,deadline).thenApply(reply->{
                if(reply.kind().equals("SOURCE_OFFER")) {
                    var offer=object(reply.value().get("payload"));
                    if(offer.get("kind").equals("CAPSULE"))assertNull(offers.put((String)offer.get("id"),offer));
                }
                return reply;
            }));
            var captured=new AtomicReference<Cut>();var foreign=new AtomicReference<Path>();
            local.localStorageCut.set(event->{
                if(!event.equals("INSTALL_BEFORE_RETURN"))return;
                try {
                    var cut=new Cut(live(local.budgets.getFirst()),packets(local.driverScratch));
                    assertTrue(captured.compareAndSet(null,cut));originalReceiving(cut,offers,size/2);
                    if(damage)foreign.set(Files.writeString(cut.files.keySet().iterator().next().getParent().resolve("foreign"),
                            "not-owned-by-receiver",StandardOpenOption.CREATE_NEW));
                }catch(IOException error){throw new UncheckedIOException(error);}
            });
            if(!damage) {
                var selected=driver.run();assertEquals(size/2+1,list(selected.value().get("sources")).size());
                assertNotNull(captured.get());assertArrayEquals(selected.bytes(),driver.selection().bytes());
                drained(local,offers);
            } else {
                var failure=assertThrows(IOException.class,driver::run);
                assertTrue(failure.getMessage().contains("peer cleanup failed"),failure.toString());
                assertNotNull(captured.get());assertNotNull(foreign.get());
                assertEquals("activation driver installation unavailable",assertThrows(IllegalArgumentException.class,driver::selection).getMessage());
                Path packet=foreign.get().getParent().resolve("source.gscp");
                String digest=captured.get().files.get(packet);assertEquals(digest,hash(Files.readAllBytes(packet)));
                String id=offers.entrySet().stream().filter(v->v.getValue().get("digest").equals(digest)).findFirst().orElseThrow().getKey();
                var charge=captured.get().charges.get(new Key(MembershipResources.Unit.SOURCE,id));
                assertEquals(charge,live(local.budgets.getFirst()).get(new Key(MembershipResources.Unit.SOURCE,id)));
                var durable=V53ReplayFilesTest.files(local.group.fixture.request.targets().getFirst().replicaDirectory());
                assertThrows(IOException.class,driver::close);
                assertEquals("not-owned-by-receiver",Files.readString(foreign.get()));
                assertEquals(charge,live(local.budgets.getFirst()).get(new Key(MembershipResources.Unit.SOURCE,id)));
                Files.delete(foreign.get());driver.close(); // Repair only the injected obstruction; drain stays production-owned.
                drained(local,offers);
                assertEquals(durable,V53ReplayFilesTest.files(local.group.fixture.request.targets().getFirst().replicaDirectory()));
                assertEquals("activation driver closed/interrupted",assertThrows(IOException.class,driver::selection).getMessage());
            }
            assertEquals(1,driver.campaigns());
        }
    }
    @ParameterizedTest @ValueSource(ints={3,4,5})
    void selectedReceivingCopiesDrainBeforeSuccessfulReturn(int size)throws Exception {check(size,false);}
    @Test void cleanupRefusalRetainsOriginalUntilExternalCloseCanDrain()throws Exception {check(3,true);}

    @Test void nativeRemoveDrainsBeforeIntentFinalAndNewStableBarrier()throws Exception {
        var helper=new V53TransitionRoundDriverTest();helper.temp=temp;var ordinal=new AtomicInteger();
        var milestones=new ArrayList<String>();
        try(var network=helper.network("SEALED");var round=helper.driver(network,ordinal,(event,record)->{
            if(!event.equals("INSTALLED") && !event.equals("SLOT_BEGIN") && !event.equals("BEFORE_READY"))return;
            // These are the real parent/child activation scopes, not unrelated
            // incoming endpoint scratch or installed generation directories.
            try(var dirs=Files.list(temp)) {
                var scopes=dirs.filter(p->p.getFileName().toString().startsWith("transition-")).toList();
                assertEquals(1,scopes.size());assertTrue(packets(scopes.getFirst()).isEmpty(),event);
            }
            milestones.add(event.equals("SLOT_BEGIN")?(String)record.value().get("kind"):event);
        })) {
            var completed=round.start();assertEquals(3,ordinal.get());
            assertEquals(List.of("INSTALLED","INTENT","INSTALLED","FINAL","INSTALLED","BARRIER","BEFORE_READY"),milestones);
            assertEquals(MembershipRoundDriver.State.READY,round.state());
            assertArrayEquals(completed.bytes(),round.readiness().bytes());
            var context=network.owners.getFirst().activationContext();
            assertEquals(7L,context.cut.get("index"));assertNull(context.catalog.get("active"));
            assertEquals("COMPLETED",object(list(context.catalog.get("results")).getLast()).get("phase"));
            Files.write(network.f.raw.resolve("transition-round-result.json"),canonical(Map.of("status","PASS","kind","REMOVE","profile","4-REMOVE","activations",3,
                    "internalReady",true,"publicReady",false,"originalBudgetSeconds",600),65536));
        }
    }
}
