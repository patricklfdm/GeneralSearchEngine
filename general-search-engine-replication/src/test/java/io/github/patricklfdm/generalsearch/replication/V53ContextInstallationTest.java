package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextInstallationTest {
    @TempDir static Path fixtures;
    @TempDir Path temp;
    static V53ContextPublicationTest.Scenario reference;
    static Path selected;
    static List<MembershipSelection.Source> offered;
    static Map<String,byte[]> images;
    @BeforeAll static void prepare()throws Exception {
        reference=new V53ContextPublicationTest().scenario();selected=fixtures.resolve("selected");
        V53JournalApplicationTest.copy(reference.evidence().resolve("carried-snapshots/source-retired"),selected);
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(selected,n,e->{})){owner.prepareCurrent(ballot(22));}
        var sources=new ArrayList<MembershipSelection.Source>();images=new TreeMap<>();
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(selected,n,e->{})) {
            var source=owner.originalSource();sources.add(source);
            for(String hash:source.capsule.packet.images().keySet())images.put(hash,Files.readAllBytes(selected.resolve("node-"+n+"/sources/"+source.basis.value().get("basisId")+"/"+hash+".image")));
        }
        offered=List.copyOf(sources);
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(selected,n,e->{})){owner.selectCurrent(offered,List.of());}
    }
    static Map<String,Object> ballot(long n){return reference.seed().fixture().f.initial.application.f.f.f.fixture.source.ballot(n);}
    static MembershipGrantJournal open(Path group,int n,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=reference.seed().fixture().f;assertEquals(0,f.resources.usage().leases());
        return MembershipGrantJournal.openContextual(group.resolve("node-"+n),f.initial.application.f.f.f.root(),V53DeclarationsTest.node(n),f.resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,e->{V53RetirementImagesTest.bounded(f.resources);cut.at(e);});
    }
    Path copy(String name)throws Exception {Path p=temp.resolve(name);V53JournalApplicationTest.copy(selected,p);return p;}
    static void snapshot(Path group,Path path)throws Exception {V53JournalApplicationTest.copy(group,path);}
    static void unchanged(Path group,int n,MembershipGrantJournal owner)throws Exception {
        assertArrayEquals(Files.readAllBytes(selected.resolve("node-"+n+"/pending.accept")),owner.retainPendingContext().vote().bytes());
    }
    @Test void reusedOriginalSlotInstallsAndRetiresIntermediateBeforeExactReacceptance()throws Exception {
        Path group=copy("clean"),raw=Path.of("target/v53-context-installation/run-"+UUID.randomUUID());Files.createDirectories(raw);
        snapshot(reference.evidence(),raw.resolve("reference"));snapshot(group,raw.resolve("selected"));
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
            var manifest=owner.installCurrent(offered,List.of(),images);
            assertEquals("a",manifest.value().get("generation"));
            assertArrayEquals(manifest.bytes(),owner.installCurrent(offered,List.of(),images).bytes());unchanged(group,n,owner);
            new V53MembershipOwnershipTest().probe(group.resolve("node-"+n+"/replica.lock"));
        }
        snapshot(group,raw.resolve("installed"));
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
            unchanged(group,n,owner);assertTrue(owner.retireContextOriginal().isPresent());unchanged(group,n,owner);
        }
        snapshot(group,raw.resolve("retired"));
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
            var accepted=owner.acceptRetainedCurrent(reference.seed().entry(),reference.seed().payload());
            assertEquals(accepted,owner.acceptRetainedCurrent(reference.seed().entry(),reference.seed().payload()));
            assertTrue(owner.governingFloor().isEmpty());assertEquals(7,reference.seed().fixture().f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
        }
        snapshot(group,raw.resolve("accepted"));
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(group.resolve("node-"+n+"/pending.accept")));
            assertEquals(22L,object(vote.accept().value().get("ballot")).get("counter"));
            assertArrayEquals(reference.seed().entry().bytes(),vote.entry().bytes());assertTrue(owner.currentCertificate().isEmpty());
        }
        assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-installation-v1","status","PASS","nodes",3,
                "installedBallot",22,"originalVote",20,"intermediateBallot",21,"freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextInstallationEvidence="+raw.toAbsolutePath());
    }
    @Test void everyInstallationCutReopensAndResumesOnlyAnExplicitOriginalPlan()throws Exception {
        Path raw=Path.of("target/v53-context-installation-cuts/run-"+UUID.randomUUID());Files.createDirectories(raw);
        snapshot(reference.evidence(),raw.resolve("reference"));snapshot(selected,raw.resolve("selected"));
        for(String point:V53GenerationInstallTest.CUTS) {
            Path group=copy(point),row=Files.createDirectory(raw.resolve(point));var first=new ArrayList<String>();boolean[] armed={false};
            try(var owner=open(group,1,e->{first.add(e);if(armed[0] && e.equals(point))throw new IOException("install cut");})) {
                first.clear();armed[0]=true;assertEquals("install cut",assertThrows(IOException.class,()->owner.installCurrent(offered,List.of(),images)).getMessage());
            }
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());snapshot(group.resolve("node-1"),row.resolve("crash"));
            var second=new ArrayList<String>();assertEquals("again",assertThrows(IOException.class,()->open(group,1,e->{second.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("again");})).getMessage());
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());snapshot(group.resolve("node-1"),row.resolve("recovery-crash"));
            var resume=new ArrayList<String>();
            try(var owner=open(group,1,resume::add)) {
                V53JournalContextTest.noAck(resume);assertFalse(resume.contains("INSTALL_BEFORE_RETURN"));resume.add("OPEN_RETURNED");
                var installed=owner.installCurrent(offered,List.of(),images);resume.add("EXPLICIT_INSTALL_RETURNED");
                assertArrayEquals(installed.bytes(),owner.installCurrent(offered,List.of(),images).bytes());resume.add("EXPLICIT_INSTALL_RETURNED");unchanged(group,1,owner);
                new V53MembershipOwnershipTest().probe(group.resolve("node-1/replica.lock"));
            }
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());snapshot(group.resolve("node-1"),row.resolve("final"));
            Files.write(row.resolve("events.json"),canonical(Map.of("first",first,"recovery",second,"resume",resume),131072));
        }
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-installation-cuts-v1","status","PASS","cuts",V53GenerationInstallTest.CUTS,
                "interruptions","injected-IOException","freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextInstallationCuts="+raw.toAbsolutePath());
    }
    @Test void everyIntermediateRetirementCutPreservesOriginalContextAcrossAnotherInterruption()throws Exception {
        Path installed=temp.resolve("installed");snapshot(selected,installed);
        try(var owner=open(installed,1,e->{})){owner.installCurrent(offered,List.of(),images);}
        Path raw=Path.of("target/v53-context-intermediate-retirement/run-"+UUID.randomUUID());Files.createDirectories(raw);
        snapshot(reference.evidence(),raw.resolve("reference"));snapshot(selected,raw.resolve("selected"));snapshot(installed.resolve("node-1"),raw.resolve("installed"));
        for(String point:V53RetirementTest.CUTS) {
            Path group=temp.resolve(point),row=Files.createDirectory(raw.resolve(point));snapshot(installed,group);var first=new ArrayList<String>();boolean[] armed={false};
            try(var owner=open(group,1,e->{first.add(e);if(armed[0] && e.equals(point))throw new IOException("retire cut");})) {
                first.clear();armed[0]=true;assertEquals("retire cut",assertThrows(IOException.class,owner::retireContextOriginal).getMessage());
            }
            snapshot(group.resolve("node-1"),row.resolve("crash"));var second=new ArrayList<String>();
            assertEquals("again",assertThrows(IOException.class,()->open(group,1,e->{second.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("again");})).getMessage());
            snapshot(group.resolve("node-1"),row.resolve("recovery-crash"));var resume=new ArrayList<String>();
            try(var owner=open(group,1,resume::add)) {
                V53JournalContextTest.noAck(resume);resume.add("OPEN_RETURNED");owner.retireContextOriginal();resume.add("EXPLICIT_RETIRE_RETURNED");unchanged(group,1,owner);
            }
            snapshot(group.resolve("node-1"),row.resolve("final"));
            try(var owner=open(group,1,e->{})){owner.acceptRetainedCurrent(reference.seed().entry(),reference.seed().payload());}
            snapshot(group.resolve("node-1"),row.resolve("accepted"));assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
            Files.write(row.resolve("events.json"),canonical(Map.of("first",first,"recovery",second,"resume",resume),131072));
        }
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-intermediate-retirement-v1","status","PASS","cuts",V53RetirementTest.CUTS,
                "interruptions","injected-IOException","freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextIntermediateRetirement="+raw.toAbsolutePath());
    }
    @Test void pendingInstallationPinsMaintenanceAndRejectsChangedMaterialization()throws Exception {
        for(String cut:List.of("INSTALL_MANIFEST_WRITTEN","INSTALL_SELECTOR_WRITTEN")) {
            Path group=copy("partial-"+cut);boolean[] armed={false};
            try(var owner=open(group,1,e->{if(armed[0] && e.equals(cut))throw new IOException("partial");})) {
                armed[0]=true;assertThrows(IOException.class,()->owner.installCurrent(offered,List.of(),images));
            }
            try(var owner=open(group,1,e->{})) {
                Path node=group.resolve("node-1");var before=V53BootstrapProgressResumeTest.safeFiles(node);
                assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(ballot(23)));
                assertThrows(IllegalArgumentException.class,owner::retireContextOriginal);
                assertThrows(IllegalArgumentException.class,owner::contextFloorCopy);
                assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(reference.seed().entry(),reference.seed().payload()));
                assertThrows(IllegalArgumentException.class,()->owner.installCurrent(offered.subList(0,2),List.of(),images));
                var changed=new TreeMap<String,byte[]>();images.forEach((k,v)->changed.put(k,v.clone()));changed.values().iterator().next()[0]^=1;
                assertThrows(IllegalArgumentException.class,()->owner.installCurrent(offered,List.of(),changed));
                assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));owner.installCurrent(offered,List.of(),images);
            }
        }
    }
    @Test void higherObservationAtEveryInstallBoundaryNeverReturnsOldReceipt()throws Exception {
        for(String cut:V53GenerationInstallTest.CUTS) {
            Path group=copy("fence-"+cut);var ref=new MembershipGrantJournal[1];
            try(var owner=open(group,1,e->{if(ref[0]!=null && e.equals(cut))ref[0].observeCurrent(ballot(23));})) {
                ref[0]=owner;assertThrows(IllegalArgumentException.class,()->owner.installCurrent(offered,List.of(),images));
            }
            var events=new ArrayList<String>();try(var owner=open(group,1,events::add)) {
                V53JournalContextTest.noAck(events);owner.installCurrent(offered,List.of(),images);unchanged(group,1,owner);
            }
        }
    }
    @Test void alteredCandidateRemainsUnrepairableAndLostFloorNeverAuthorizesReusedSlot()throws Exception {
        for(String changed:List.of("manifest","selector","floor")) {
            Path group=copy("altered-"+changed);boolean[] armed={false};
            try(var owner=open(group,1,e->{if(armed[0] && e.equals("INSTALL_SELECTOR_WRITTEN"))throw new IOException("partial");})) {
                armed[0]=true;assertThrows(IOException.class,()->owner.installCurrent(offered,List.of(),images));
            }
            Path node=group.resolve("node-1");Path file=node.resolve(switch(changed) {
                case "manifest"->"generations/a/generation.gsr";case "selector"->"selector.pending.gsr";default->"floor-copies/floor.gsr";
            });byte[] bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);
            var before=V53BootstrapProgressResumeTest.safeFiles(node);
            if(changed.equals("floor"))assertThrows(IllegalArgumentException.class,()->open(group,1,e->{}));
            else try(var owner=open(group,1,e->{})) {
                assertThrows(IllegalArgumentException.class,()->owner.installCurrent(offered,List.of(),images));
            }
            assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
        }
    }
}
