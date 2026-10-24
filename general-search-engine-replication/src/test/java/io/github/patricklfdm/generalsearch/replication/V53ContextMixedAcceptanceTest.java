package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53ContextMixedAcceptanceTest {
    @TempDir Path temp;
    @Test void higherAcceptanceOfSameEntryInstallsWithoutLosingTheOlderOriginal()throws Exception {
        var driver=new V53ContextInstallationLifetimeTest();driver.reference=new V53ContextPublicationTest().scenario();
        Path group=temp.resolve("group"),raw=Path.of("target/v53-context-mixed-acceptance/run-"+UUID.randomUUID());Files.createDirectories(raw);
        driver.snapshot(driver.reference.evidence(),raw.resolve("reference"));driver.snapshot(driver.reference.evidence().resolve("carried-snapshots/source-retired"),group);
        System.out.println("v53ContextMixedAcceptanceEvidence="+raw.toAbsolutePath());System.out.flush();
        var seed=driver.reference.seed();
        for(int n:List.of(2,3))try(var owner=driver.open(group,n,e->{})){owner.acceptRetainedCurrent(seed.entry(),seed.payload());}
        driver.snapshot(group,raw.resolve("mixed"));
        for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})){owner.prepareCurrent(driver.ballot(22));}
        var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
        for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})) {
            var source=owner.originalSource();offers.add(source);
            for(String hash:source.capsule.packet.images().keySet())images.put(hash,Files.readAllBytes(group.resolve("node-"+n+"/sources/"+source.basis.value().get("basisId")+"/"+hash+".image")));
        }
        assertEquals(List.of(20L,21L,21L),offers.stream().map(s->object(s.accepted.value().get("ballot")).get("counter")).toList());
        for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})){assertEquals(seed.entry().digest(),owner.selectCurrent(offers,List.of()).value().get("nextEntry"));}
        driver.snapshot(group,raw.resolve("selected"));
        for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})) {
            var installed=owner.installCurrent(offers,List.of(),images);assertArrayEquals(installed.bytes(),owner.installCurrent(offers,List.of(),images).bytes());
            assertEquals(offers.get(1).accepted.digest(),installed.value().get("ownedTail"));owner.retainPendingContext();
        }
        driver.snapshot(group,raw.resolve("installed"));
        var copies=new TreeMap<Integer,MembershipFloor.Copy>();
        for(int n:List.of(2,3))try(var owner=driver.open(group,n,e->{})){copies.put(n,owner.contextFloorCopy());}
        for(int n:List.of(2,3))try(var owner=driver.open(group,n,e->{})){owner.establishContextFloor(List.of(copies.get(2),copies.get(3)));}
        driver.snapshot(group,raw.resolve("floors"));
        for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})){owner.retireContextOriginal();}
        driver.snapshot(group,raw.resolve("retired"));
        // Nodes 2/3 no longer need their original ballot-21 source after floor22.
        for(int n:List.of(2,3))try(var owner=driver.open(group,n,e->{})) {
            var old=MembershipPendingAccept.decode(Files.readAllBytes(group.resolve("node-"+n+"/pending.accept")));
            owner.retireSource((String)old.promise().value().get("basisId"));
        }
        driver.snapshot(group,raw.resolve("predecessors-retired"));
        for(int counter:List.of(23,24)) {
            Path row=Files.createDirectory(raw.resolve("round-"+counter));var prior=new TreeMap<Integer,String>();
            var next=new ArrayList<MembershipSelection.Source>();var nextImages=new TreeMap<String,byte[]>();
            for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})) {
                prior.put(n,(String)owner.originalBasis().orElseThrow().value().get("basisId"));owner.prepareCurrent(driver.ballot(counter));
                var offered=owner.originalSource();next.add(offered);
                assertEquals(21L,object(offered.accepted.value().get("ballot")).get("counter"));
                for(String hash:offered.capsule.packet.images().keySet())nextImages.put(hash,Files.readAllBytes(group.resolve("node-"+n+"/sources/"+offered.basis.value().get("basisId")+"/"+hash+".image")));
            }
            driver.snapshot(group,row.resolve("captured"));
            for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})){owner.selectCurrent(next,List.of());}
            driver.snapshot(group,row.resolve("selected"));
            for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})){owner.installCurrent(next,List.of(),nextImages);}
            driver.snapshot(group,row.resolve("installed"));
            for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})){owner.retireContextOriginal();}
            driver.snapshot(group,row.resolve("generation-retired"));
            for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})) {
                if(counter>23 || n==1)owner.retireSource(prior.get(n));
                else {
                    var before=V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-"+n));
                    assertThrows(IllegalArgumentException.class,()->owner.retireSource(prior.get(n)));
                    assertEquals(before,V53BootstrapProgressResumeTest.safeFiles(group.resolve("node-"+n)));
                }
                assertArrayEquals(Files.readAllBytes(raw.resolve("mixed/node-"+n+"/pending.accept")),owner.retainPendingContext().vote().bytes());
            }
            driver.snapshot(group,row.resolve("source-retired"));
        }
        for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})) {
            var accepted=owner.acceptRetainedCurrent(seed.entry(),seed.payload());assertEquals(accepted,owner.acceptRetainedCurrent(seed.entry(),seed.payload()));
        }
        driver.snapshot(group,raw.resolve("accepted"));
        var helper=new V53ContextInstalledPublicationTest();helper.driver=driver;helper.group=group;helper.raw=raw;
        helper.finish(helper.apply(seed.entry(),seed.payload()));helper.snapshot("published");
        for(int n:List.of(1,2,3))try(var owner=driver.open(group,n,e->{})) {
            var copy=owner.floorCopyCurrent();assertEquals(2L,copy.capsule.context.cut.get("index"));assertEquals(43L,copy.capsule.context.catalog.get("applicationSequence"));
            var app=seed.fixture().f.initial.application.app;var state=app.read(copy.fileBytes(copy.capsule.terminal().application()+".image"),"mixed-context-"+n);
            assertEquals(1,state.documents().stream().filter(d->d.equals(new Doc(303,"staged-original"))).count());
        }
        assertEquals(0,seed.fixture().f.resources.usage().leases());
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-mixed-acceptance-v1","status","PASS","nodes",3,
                "originalAccepts",List.of(20,21,21),"installedBallot",24,"entryOrigin",20,"publishedCut",2,"applicationSequence",43,"runtimeEnabled",false),16384));
        V53ContextMixedRecovery.run(driver,raw,Files.createDirectory(temp.resolve("recovery")));
    }
}
