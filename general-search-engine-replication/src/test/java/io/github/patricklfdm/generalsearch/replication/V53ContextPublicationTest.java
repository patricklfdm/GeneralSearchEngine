package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Three actual contextual owners through voting, typed publication and continuation. */
class V53ContextPublicationTest {
    static final List<Integer> NODES=List.of(1,2,3);
    static MembershipGrantJournal open(V53RoundStorageTest.Fixture f,int n)throws Exception {
        assertEquals(0,f.f.resources.usage().leases());
        return MembershipGrantJournal.openContextual(f.f.node(n),f.f.initial.application.f.f.f.root(),V53DeclarationsTest.node(n),f.f.resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.f.observations),MembershipGrantJournal.MAXIMUM,
                event->V53RetirementImagesTest.bounded(f.f.resources));
    }
    record Scenario(Path evidence,V53StagedApplicationTest.Seed seed) {}
    @Test void allContextOwnersFormNewProofApplyOncePublishAndContinue()throws Exception {scenario();}
    Scenario scenario()throws Exception {
        Path root=Path.of("target/v53-context-publication/run-"+UUID.randomUUID());Files.createDirectories(root);
        var seed=V53StagedApplicationTest.seed(root);var f=seed.fixture();
        Files.write(root.resolve("entry.gsr"),seed.entry().bytes());Files.write(root.resolve("payload.bin"),seed.payload());
        V53CarriedPublicationTest.snapshot(f,"old-certified");var setup=f.f.prepare(1);V53CarriedPublicationTest.snapshot(f,"prepared");
        for(int n:NODES)try(var owner=f.f.open(n)){owner.installCurrent(setup.sources(),List.of(),setup.images());}
        V53CarriedPublicationTest.snapshot(f,"installed");
        for(int n:NODES)try(var owner=open(f,n)){owner.retainPendingContext();}
        V53CarriedPublicationTest.snapshot(f,"context");
        var copies=new TreeMap<Integer,MembershipFloor.Copy>();
        for(int n:NODES)try(var owner=open(f,n)){copies.put(n,owner.contextFloorCopy());}
        for(int n:NODES)try(var owner=open(f,n)){owner.establishContextFloor(List.of(copies.get(n),copies.get(n%3+1)));}
        V53CarriedPublicationTest.snapshot(f,"context-floor");
        for(int n:NODES)try(var owner=open(f,n)){owner.retireContextOriginal();}
        V53CarriedPublicationTest.snapshot(f,"context-retired");
        for(int n:NODES)try(var owner=open(f,n)){owner.retireSource(setup.obsolete().get(n));}
        V53CarriedPublicationTest.snapshot(f,"source-retired");
        for(int n:NODES)try(var owner=open(f,n)) {
            var accepted=owner.acceptRetainedCurrent(seed.entry(),seed.payload());assertEquals(accepted,owner.acceptRetainedCurrent(seed.entry(),seed.payload()));
            assertEquals(6,f.f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.governingFloor().isEmpty());
            new V53MembershipOwnershipTest().probe(f.f.node(n).resolve("replica.lock"));
        }
        V53CarriedPublicationTest.snapshot(f,"reaccepted");
        var publication=f.apply(seed.entry(),seed.payload());
        for(var value:publication.applied().values())assertNotEquals(seed.phased().certificate().digest(),value.plan().originalCertificate().digest());
        V53CarriedPublicationTest.finish(f,publication);V53CarriedPublicationTest.snapshot(f,"published");
        var barrier=new TreeMap<>(f.entry("BARRIER",new byte[0]).value());barrier.put("origin",setup.ballot());
        V53CarriedPublicationTest.finish(f,f.apply(decode(encode("records","ENTRY",barrier),"records","ENTRY"),new byte[0]));
        V53CarriedPublicationTest.snapshot(f,"continued");
        for(int n:NODES)try(var owner=open(f,n)) {
            var copy=owner.floorCopyCurrent();assertEquals(3L,copy.capsule.context.cut.get("index"));assertEquals(43L,copy.capsule.context.catalog.get("applicationSequence"));
            var state=f.f.initial.application.app.read(copy.fileBytes(copy.capsule.terminal().application()+".image"),"context-final-"+n);
            assertEquals(1,state.documents().stream().filter(d->d.equals(new Doc(303,"staged-original"))).count());
            assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
            assertNull(owner.prepareCurrent(f.f.initial.application.f.f.f.fixture.source.ballot(22)).value().get("accepted"));
        }
        V53CarriedPublicationTest.snapshot(f,"fresh");assertEquals(0,f.f.resources.usage().leases());
        Files.write(root.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-publication-v1","status","PASS",
                "nodes",3,"entryOrigin",20,"acceptBallot",21,"publishedCut",3,"applicationSequence",43,"freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextPublicationEvidence="+root.toAbsolutePath());return new Scenario(root,seed);
    }
}
