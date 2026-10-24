package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53ContextInstallationLifetimeTest {
    @TempDir Path temp;
    V53ContextPublicationTest.Scenario reference;
    MembershipGrantJournal open(Path group,int n,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=reference.seed().fixture().f;assertEquals(0,f.resources.usage().leases());
        return MembershipGrantJournal.openContextual(group.resolve("node-"+n),f.initial.application.f.f.f.root(),V53DeclarationsTest.node(n),f.resources,
                (r,p,i)->MembershipCapsule.verify(r,p,i,f.observations),MembershipGrantJournal.MAXIMUM,e->{V53RetirementImagesTest.bounded(f.resources);cut.at(e);});
    }
    Map<String,Object> ballot(long n){return reference.seed().fixture().f.initial.application.f.f.f.fixture.source.ballot(n);}
    void snapshot(Path group,Path path)throws Exception {V53JournalApplicationTest.copy(group,path);}
    record Scenario(Path evidence,Path group) {}
    @Test void repeatedSlotsAndSourceReclamationLeaveRoomForTheExactSuccessor()throws Exception {sourceRetirementCuts(scenario().evidence());}
    Scenario scenario()throws Exception {
        reference=new V53ContextPublicationTest().scenario();Path group=temp.resolve("group");
        snapshot(reference.evidence().resolve("carried-snapshots/source-retired"),group);
        Path raw=Path.of("target/v53-context-installation-lifetime/run-"+UUID.randomUUID());Files.createDirectories(raw);snapshot(reference.evidence(),raw.resolve("reference"));
        System.out.println("v53ContextInstallationLifetimeEvidence="+raw.toAbsolutePath());
        var floorIds=new TreeMap<Integer,String>();
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})){floorIds.put(n,(String)owner.originalBasis().orElseThrow().value().get("basisId"));}
        for(int counter=22;counter<=27;counter++) {
            Path row=Files.createDirectory(raw.resolve("round-"+counter));var prior=new TreeMap<Integer,String>();
            var sources=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
            for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
                prior.put(n,(String)owner.originalBasis().orElseThrow().value().get("basisId"));owner.prepareCurrent(ballot(counter));
                var source=owner.originalSource();sources.add(source);
                for(String h:source.capsule.packet.images().keySet())images.put(h,Files.readAllBytes(group.resolve("node-"+n+"/sources/"+source.basis.value().get("basisId")+"/"+h+".image")));
            }
            snapshot(group,row.resolve("captured"));
            for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})){owner.selectCurrent(sources,List.of());}
            snapshot(group,row.resolve("selected"));
            if(counter>22)for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
                var before=V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-"+n));
                assertThrows(IllegalArgumentException.class,()->owner.retireSource(prior.get(n)));
                assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-"+n)));
            }
            for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})){owner.installCurrent(sources,List.of(),images);}
            snapshot(group,row.resolve("installed"));
            for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})){owner.retireContextOriginal();}
            snapshot(group,row.resolve("generation-retired"));
            for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
                Path node=group.resolve("node-"+n);var before=V53BootstrapProgressResumeTest.safeFiles(node);
                assertThrows(IllegalArgumentException.class,()->owner.retireSource(floorIds.get(n)));
                String latest=(String)owner.originalBasis().orElseThrow().value().get("basisId");assertThrows(IllegalArgumentException.class,()->owner.retireSource(latest));
                assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(node));
                if(counter>22)owner.retireSource(prior.get(n));
                assertArrayEquals(Files.readAllBytes(reference.evidence().resolve("carried-snapshots/source-retired/node-"+n+"/pending.accept")),owner.retainPendingContext().vote().bytes());
                assertEquals(6,reference.seed().fixture().f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }
            snapshot(group,row.resolve("source-retired"));assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
            System.out.println("v53ContextInstallationLifetimeRound="+counter+" PASS");
        }
        for(int n:V53ContextPublicationTest.NODES)try(var owner=open(group,n,e->{})) {
            owner.acceptRetainedCurrent(reference.seed().entry(),reference.seed().payload());
            assertEquals(7,reference.seed().fixture().f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));assertTrue(owner.governingFloor().isEmpty());
        }
        snapshot(group,raw.resolve("accepted"));assertEquals(0,reference.seed().fixture().f.resources.usage().leases());
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-installation-lifetime-v1","status","PASS","rounds",List.of(22,23,24,25,26,27),
                "nodes",3,"originalVote",20,"floorBallot",21,"freshProcesses",false,"runtimeEnabled",false),16384));
        System.out.println("v53ContextInstallationLifetimeEvidence="+raw.toAbsolutePath());
        return new Scenario(raw,group);
    }
    void sourceRetirementCuts(Path referenceRaw)throws Exception {
        Path raw=Path.of("target/v53-context-installed-source-cuts/run-"+UUID.randomUUID());Files.createDirectories(raw);
        snapshot(referenceRaw,raw.resolve("reference"));
        Path seed=referenceRaw.resolve("round-23/generation-retired/node-1");snapshot(seed,raw.resolve("initial"));
        System.out.println("v53ContextInstalledSourceCuts="+raw.toAbsolutePath());
        var prior=MembershipPendingContext.decode(Files.readAllBytes(referenceRaw.resolve("round-22/source-retired/node-1/pending.context")));
        String sourceId=(String)MembershipPendingContext.backingBasis(prior).value().get("basisId");
        for(String point:V53ContextSourceReleaseTest.CUTS) {
            Path group=Files.createDirectory(temp.resolve("cut-"+point)),node=group.resolve("node-1"),row=Files.createDirectory(raw.resolve(point));snapshot(seed,node);
            var first=new ArrayList<String>();var second=new ArrayList<String>();var resume=new ArrayList<String>();boolean[] armed={false};
            try(var owner=open(group,1,e->{first.add(e);if(armed[0] && e.equals(point))throw new IOException("installed source cut");})) {
                first.clear();armed[0]=true;assertEquals("installed source cut",assertThrows(IOException.class,()->owner.retireSource(sourceId)).getMessage());
            }
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());snapshot(node,row.resolve("crash"));
            assertEquals("second cut",assertThrows(IOException.class,()->open(group,1,e->{second.add(e);if(e.equals("CONTEXT_SOURCE_PARENT_FORCED"))throw new IOException("second cut");})).getMessage());
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());snapshot(node,row.resolve("recovery-crash"));
            try(var owner=open(group,1,resume::add)) {
                if(Files.exists(node.resolve("sources").resolve(sourceId)))owner.retireSource(sourceId);
                assertArrayEquals(Files.readAllBytes(seed.resolve("pending.accept")),owner.retainPendingContext().vote().bytes());
                assertEquals(6,reference.seed().fixture().f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                new V53MembershipOwnershipTest().probe(node.resolve("replica.lock"));
            }
            assertEquals(0,reference.seed().fixture().f.resources.usage().leases());snapshot(node,row.resolve("final"));
            for(var events:List.of(first,second,resume))V53JournalContextTest.noAck(events);
            Files.write(row.resolve("events.json"),canonical(Map.of("first",first,"recovery",second,"resume",resume),131072));
            System.out.println("v53ContextInstalledSourceCut="+point+" PASS");
        }
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-installed-source-cuts-v1","status","PASS",
                "cuts",V53ContextSourceReleaseTest.CUTS,"interruptions","injected-IOException","freshProcesses",false,"runtimeEnabled",false),16384));
    }
}
