package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Real retained prior-ballot votes, then native TCP activation and whole slots. */
class V53CarriedSlotDriverTest {
    @TempDir Path temp;
    static final class Stop extends IOException {}
    static void prepare(V53BootstrapPublicationTest.Fixture f,String phase)throws Exception {
        prepare(f,phase,false);
    }
    static void prepare(V53BootstrapPublicationTest.Fixture f,String phase,boolean data)throws Exception {
        f.campaign(1);
        String stop=switch(phase){case "ACCEPT" -> "proof-1";case "PROOF" -> "certificate-1";default -> "apply-1";};
        f.observer=(target,operation,event)->{if(operation.equals(stop))throw new Stop();};
        try{assertThrows(Stop.class,()->f.publish(1,data));}
        finally{f.observer=(target,operation,event)->{};}
        if(phase.equals("APPLIED"))for(var t:f.request.targets())try(var owner=f.open(t,"old-apply")) {
            owner.applyCurrent(builder().configuration(),t.materialization());
        }
        f.observations.clear();f.snapshot("old-"+phase.toLowerCase(Locale.ROOT));
        Files.writeString(f.raw.resolve("carried-phase.txt"),phase);
        if(data)Files.writeString(f.raw.resolve("carried-kind.txt"),"DATA");
    }
    V53NativeDispatchTest.Network network(String phase)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        return helper.new Network(3,ReplicationBounds.defaults(),f->prepare(f,phase));
    }
    MembershipSlotDriver driver(V53NativeDispatchTest.Network n,long started)throws Exception {
        return new MembershipSlotDriver(n.owners.getFirst(),n.endpoints.getFirst(),n.resources.getFirst(),n.bounds,n.transports.getFirst(),
            System::nanoTime,started,V53NativeDispatchTest.BUDGET,builder().configuration(),n.f.request.targets().getFirst().materialization(),
            (event,record,voters)->{
                if(event.equals("FUTURE_QUORUM_COMPLETE"))n.events.add(Map.of("node","node-1","event",event,"index",record.value().get("index"),"voters",voters.stream().sorted().toList()));
                if(event.equals("APPLIED") || event.equals("PUBLISHED"))try {
                    n.f.snapshot(event.toLowerCase(Locale.ROOT)+"-"+record.value().get("index"));
                }catch(Exception error){throw new IOException(error);}});
    }
    void complete(V53NativeDispatchTest.Network n,long started)throws Exception {
        var entry=decode(Files.readAllBytes(n.f.raw.resolve("entry-1.gsr")),"records","ENTRY");
        byte[] payload=Files.readAllBytes(n.f.raw.resolve("payload-1.bin"));
        assertEquals(entry.digest(),n.selected.value().get("nextEntry"));
        assertNotEquals(entry.value().get("origin"),n.ballot);
        n.events.add(Map.of("node","node-1","event","SLOT_BEGIN","index",1L));
        try(var driver=driver(n,started)){assertEquals("PUBLISH_ACK",driver.run(entry,payload).kind());}
        for(int index:n.voters)assertEquals(1L,n.owners.get(index).activationContext().cut.get("index"));
        var helper=new V53SlotDriverTest();helper.temp=temp;var barrier=helper.input(n,false);
        assertEquals(n.ballot,barrier.entry().value().get("origin"));assertEquals(2L,barrier.entry().value().get("index"));
        n.events.add(Map.of("node","node-1","event","SLOT_BEGIN","index",2L));
        try(var driver=driver(n,started)){assertEquals("PUBLISH_ACK",driver.run(barrier.entry(),barrier.payload()).kind());}
        for(int index:n.voters)assertEquals(2L,n.owners.get(index).activationContext().cut.get("index"));
        assertEquals(0L,n.owners.get(2).activationContext().cut.get("index"));
        Files.write(n.f.raw.resolve("carried-result.json"),canonical(Map.of("status","PASS","carried",entry.digest(),"slots",2,"publicReady",false),4096));
    }
    @Test void inheritedAppliedCertificateReacceptsBeforeFloorAndFreshBarrier()throws Exception {
        try(var n=network("APPLIED")){long started=System.nanoTime();n.activate();complete(n,started);}
    }
    @Test void inheritedAcceptReacceptsBeforeFloorAndFreshBarrier()throws Exception {
        try(var n=network("ACCEPT")){long started=System.nanoTime();n.activate();complete(n,started);}
    }
    @Test void inheritedProofReacceptsBeforeFloorAndFreshBarrier()throws Exception {
        try(var n=network("PROOF")){long started=System.nanoTime();n.activate();complete(n,started);}
    }
    @Test void inheritedCertificateReacceptsBeforeFloorAndFreshBarrier()throws Exception {
        try(var n=network("CERTIFICATE")){long started=System.nanoTime();n.activate();complete(n,started);}
    }
    @Test void changedEntryOrPayloadCannotAuthorizeDerivedCleanup()throws Exception {
        try(var n=network("APPLIED")) {
            n.activate();var target=n.f.request.targets().getFirst();var own=n.owners.getFirst();
            var entry=decode(Files.readAllBytes(n.f.raw.resolve("entry-1.gsr")),"records","ENTRY");
            var before=V53ReplayFilesTest.files(target.replicaDirectory());
            var changed=new TreeMap<>(entry.value());changed.put("origin",n.ballot);
            assertThrows(IllegalArgumentException.class,()->own.acceptCurrent(decode(encode("records","ENTRY",changed),"records","ENTRY"),
                new byte[0],builder().configuration(),target.materialization()));
            assertThrows(IllegalArgumentException.class,()->own.acceptCurrent(entry,new byte[]{1},builder().configuration(),target.materialization()));
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            assertTrue(Files.isDirectory(target.replicaDirectory().resolve("applied-end")));
        }
    }
    @Test void originalCarriedRecoveryTransfersOnlyAcceptanceAndIsIdempotent()throws Exception {
        V53BootstrapPublicationTest.Fixture retained;byte[] exactVote;
        try(var n=network("APPLIED")) {
            retained=n.f;
            n.activate();var target=n.f.request.targets().getFirst();var owner=n.owners.getFirst();
            var original=MembershipPendingAccept.decode(Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
            assertNotNull(original.certificate());
            assertFalse(owner.preGrantMaintenanceRequired());
            owner.recoverCarriedAcceptance(builder().configuration(),target.materialization());
            var recovered=MembershipPendingAccept.decode(Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
            assertArrayEquals(original.entry().bytes(),recovered.entry().bytes());assertArrayEquals(original.payload(),recovered.payload());
            assertEquals(n.ballot,recovered.accept().value().get("ballot"));assertEquals(n.selected.digest(),recovered.selected().digest());
            assertNull(recovered.proof());assertNull(recovered.certificate());
            exactVote=recovered.bytes();
            for(var frame:List.of(original.entry(),original.accept(),original.proof(),original.certificate()))
                assertArrayEquals(frame.bytes(),owner.originalSource().capsule.packet.objectBytes(frame.digest()));
            assertEquals(0L,owner.activationContext().cut.get("index"));
            assertFalse(owner.publishedMaintenanceRequired());assertTrue(owner.preGrantMaintenanceRequired());
            var permit=owner.preGrantMaintenance(n.resources.getFirst());permit.check();
            var before=V53ReplayFilesTest.files(target.replicaDirectory());
            owner.recoverCarriedAcceptance(builder().configuration(),target.materialization());
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            var usage=n.resources.getFirst().usage();owner.prepareCurrent(n.ballot);
            assertEquals(usage,n.resources.getFirst().usage());
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
            var higher=new TreeMap<>(n.ballot);higher.put("counter",owner.reserveCounter());
            var basis=owner.prepareCurrent(higher);
            assertThrows(IllegalArgumentException.class,permit::check);
            assertTrue(owner.preGrantMaintenanceRequired());var renewed=owner.preGrantMaintenance(n.resources.getFirst());renewed.check();
            assertEquals(recovered.accept().digest(),basis.value().get("accepted"));
            assertArrayEquals(recovered.bytes(),Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
            assertEquals(0L,owner.activationContext().cut.get("index"));
            var fenced=new TreeMap<>(higher);fenced.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(fenced);
            assertThrows(MembershipGrantJournal.HigherBallot.class,renewed::check);
        }
        var target=retained.request.targets().getFirst();
        try(var reopened=retained.open(target,"reopen-transferred-after-new-grant")) {
            assertArrayEquals(exactVote,Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
            assertTrue(reopened.preGrantMaintenanceRequired());reopened.preGrantMaintenance(retained.resources).check();
            assertEquals(0L,reopened.activationContext().cut.get("index"));
        }
        assertEquals(0,retained.resources.usage().leases());
    }
    @Test void observedHigherBallotRefusesCarriedRecoveryBeforeCleanup()throws Exception {
        try(var n=network("APPLIED")) {
            n.activate();var target=n.f.request.targets().getFirst();var owner=n.owners.getFirst();
            var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(higher);
            var before=V53ReplayFilesTest.files(target.replicaDirectory());
            assertThrows(IllegalArgumentException.class,()->owner.recoverCarriedAcceptance(builder().configuration(),target.materialization()));
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
        }
    }
    @Test void newerGrantKeepsExistingAppliedBytes()throws Exception {
        try(var n=network("APPLIED")) {
            var target=n.f.request.targets().getFirst();var owner=n.owners.getFirst();
            Path applied=target.replicaDirectory().resolve(MembershipAppliedEndFiles.DIRECTORY);
            var endBefore=V53ReplayFilesTest.files(applied);assertFalse(endBefore.isEmpty());
            var vote=Files.readAllBytes(target.replicaDirectory().resolve("pending.accept"));
            var next=new TreeMap<>(object(owner.originalBasis().orElseThrow().value().get("ballot")));
            next.put("counter",owner.reserveCounter());owner.prepareCurrent(next);
            assertEquals(endBefore,V53ReplayFilesTest.files(applied));
            assertArrayEquals(vote,Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
        }
    }
    @Test void higherBallotDuringRemoteCleanupCannotProduceANewVote()throws Exception {
        try(var n=network("APPLIED")) {
            long started=System.nanoTime();n.activate();var target=n.f.request.targets().get(1);var old=Files.readAllBytes(target.replicaDirectory().resolve("pending.accept"));
            n.hook.set(event->{if(event.equals("NATIVE_RETIREMENT_CERTIFICATE_RETAINED")) {
                var higher=new TreeMap<>(n.ballot);higher.put("counter",number(higher.get("counter"))+1);n.owners.get(1).observeCurrent(higher);
            }});
            try(var driver=driver(n,started)) {
                var entry=decode(Files.readAllBytes(n.f.raw.resolve("entry-1.gsr")),"records","ENTRY");
                assertThrows(Exception.class,()->driver.run(entry,new byte[0]));assertTrue(driver.published().isEmpty());
            }
            assertArrayEquals(old,Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
            assertEquals(0L,n.owners.getFirst().activationContext().cut.get("index"));
            assertTrue(n.events.stream().noneMatch(v->v.get("event").equals("PROOF_PARENT_FORCED")));
        }
    }
}
