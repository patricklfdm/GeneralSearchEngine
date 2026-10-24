package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53ContextInstalledPublicationTest {
    @TempDir Path temp;
    static final List<Integer> NODES=V53ContextPublicationTest.NODES;
    V53ContextInstallationLifetimeTest driver;
    Path group,raw;
    MembershipGrantJournal open(int n)throws Exception {return driver.open(group,n,e->{});}
    void snapshot(String name)throws Exception {
        Path path=raw.resolve("carried-snapshots/"+name);Files.createDirectories(path.getParent());driver.snapshot(group,path);
    }
    V53RoundStorageTest.Publication apply(Decoded entry,byte[] payload)throws Exception {
            var f=driver.reference.seed().fixture().f;var accepts=new HashSet<Owned>();Decoded accept=null;
            for(int n:NODES)try(var store=open(n)) {
                accepts.add(store.acceptCurrent(entry,payload));accept=MembershipPendingAccept.decode(Files.readAllBytes(group.resolve("node-"+n).resolve("pending.accept"))).accept();
            }
            String root=f.initial.application.f.f.f.root().manifestDigest();
            var proofFields=new TreeMap<>(Objects.requireNonNull(accept).value());proofFields.put("accepts",V53PublicationLifetimeTest.witnesses(root,"ACCEPT",accept,accepts));
            var proof=decode(encode("records","PROOF",proofFields),"records","PROOF");var proofs=new HashSet<Owned>();
            for(int n:NODES)try(var store=open(n)){proofs.add(store.proveCurrent(proof,accepts));}
            var fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(root,"PROOF",proof,proofs));
            var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");var phased=new HashSet<>(accepts);phased.addAll(proofs);f.observations.addAll(phased);
            for(int n:NODES)try(var store=open(n)){store.certifyCurrent(certificate,phased);}
            var applied=new TreeMap<Integer,MembershipGrantJournal.Applied>();var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
            var lower=new TreeMap<Long,List<MembershipAppliedEndFiles.ParentEndorsement>>();
            for(int n:NODES)try(var store=open(n)) {
                var result=store.applyCurrent(f.initial.application.app.configuration(),f.initial.application.app.storage(),phased);applied.put(n,result);
                acks.add(result.endorsement().acknowledgement());owned.add(result.endorsement().owned());
                var ends=new ArrayList<>(result.endorsement().ancestors());result.endorsement().parent().ifPresent(ends::add);
                for(var end:ends)lower.computeIfAbsent(number(object(end.statement().value().get("start")).get("index")),k->new ArrayList<>()).add(end);
            }
            f.observations.addAll(owned);var bridges=new ArrayList<MembershipSelection.Bridge>();
            for(var group:lower.values()) {
                var observations=group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::owned).collect(java.util.stream.Collectors.toSet());
                f.observations.addAll(observations);bridges.add(new MembershipSelection.Bridge(group.getFirst().statement(),group.stream().map(MembershipAppliedEndFiles.ParentEndorsement::acknowledgement).toList(),observations));
            }
            for(int n:NODES) {
                Path original=raw.resolve("originals/slot-"+entry.value().get("index")+"/node-"+n);
                Files.createDirectories(original.getParent());V53JournalApplicationTest.copy(group.resolve("node-"+n),original);
            }
            return new V53RoundStorageTest.Publication(applied,acks,owned,bridges);
        }
    void maintain(Map<Integer,String> obsolete)throws Exception {
        var copies=new TreeMap<Integer,MembershipFloor.Copy>();
        for(int n:NODES)try(var owner=open(n)){copies.put(n,owner.floorCopyCurrent());}
        for(int n:NODES)try(var owner=open(n)) {
            owner.establishFloor(List.of(copies.get(n),copies.get(n%3+1)));owner.retireInactive();
            if(obsolete!=null)owner.retireSource(obsolete.get(n));
            owner.releaseFloor();owner.rotateJournal();
        }
    }
    void finish(V53RoundStorageTest.Publication publication)throws Exception {
        for(int n:NODES)try(var owner=open(n)) {
            var first=publication.publish(owner,n);assertArrayEquals(first.bytes(),publication.publish(owner,n).bytes());
            assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
        }
        maintain(null);
    }
    @Test void repeatedInstallationPublishesTheOriginalExactlyOnceAndContinues()throws Exception {
        driver=new V53ContextInstallationLifetimeTest();driver.temp=Files.createDirectory(temp.resolve("lifetime"));
        var lifetime=driver.scenario();group=lifetime.group();
        raw=Path.of("target/v53-context-installed-publication/run-"+UUID.randomUUID());Files.createDirectories(raw);
        driver.snapshot(lifetime.evidence(),raw.resolve("reference"));System.out.println("v53ContextInstalledPublicationEvidence="+raw.toAbsolutePath());
        var seed=driver.reference.seed();var old=new TreeMap<Integer,String>();
        for(int n:NODES) {
            var context=MembershipPendingContext.decode(Files.readAllBytes(driver.reference.evidence().resolve("carried-snapshots/source-retired/node-"+n+"/pending.context")));
            old.put(n,(String)MembershipPendingContext.backingBasis(context).value().get("basisId"));
        }
        var first=apply(seed.entry(),seed.payload());finish(first);snapshot("published");
        maintain(old);snapshot("reclaimed");
        Decoded barrier;
        try(var owner=open(1)) {
            var c=owner.floorCopyCurrent().capsule.context;
            barrier=decode(encode("records","ENTRY",Map.of("root",c.root,"authority",c.authority(),"index",3L,"previous",c.cut.get("entry"),
                    "origin",driver.ballot(27),"kind","BARRIER","payload",hash(new byte[0]))),"records","ENTRY");
        }
        finish(apply(barrier,new byte[0]));snapshot("continued");
        for(int n:NODES)try(var owner=open(n)) {
            var copy=owner.floorCopyCurrent();assertEquals(3L,copy.capsule.context.cut.get("index"));assertEquals(43L,copy.capsule.context.catalog.get("applicationSequence"));
            var app=seed.fixture().f.initial.application.app;
            var state=app.read(copy.fileBytes(copy.capsule.terminal().application()+".image"),"installed-context-final-"+n);
            assertEquals(1,state.documents().stream().filter(d->d.equals(new Doc(303,"staged-original"))).count());
            assertEquals(2,seed.fixture().f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            assertTrue(owner.currentCertificate().isEmpty());assertTrue(owner.currentOwnedTail().isEmpty());
            assertNull(owner.prepareCurrent(driver.ballot(28)).value().get("accepted"));
        }
        snapshot("fresh");assertEquals(0,seed.fixture().f.resources.usage().leases());
        Files.write(raw.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-context-installed-publication-v1","status","PASS","nodes",3,
                "entryOrigin",20,"acceptBallot",27,"publishedCut",3,"applicationSequence",43,"freshBallot",28,"freshProcesses",false,"runtimeEnabled",false),16384));
    }
}
