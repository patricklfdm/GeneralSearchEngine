package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual admitted context outlives its original generation, then a majority advances. */
class V53CoveredContextTest {
    @TempDir Path temp;
    record Prepared(V53BootstrapPublicationTest.Fixture f,V53DistinctMinorityTest.Installation installation) {}
    record Original(V53BootstrapPublicationTest.Fixture f,Decoded entry,byte[] payload) {}
    Original original(int size,boolean backup,String phase)throws Exception {
        Path raw=Path.of("target/v53-covered-context/run-"+UUID.randomUUID());Files.createDirectories(raw);
        System.out.println("v53CoveredContextEvidence="+raw.toAbsolutePath());
        Files.write(raw.resolve("profile.json"),canonical(Map.of("size",size,"backup",backup,"phase",phase),16384));
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("group-"+UUID.randomUUID())),raw,size,backup);
        try {
            f.campaign(1);var all=f.request.targets();var majority=all.subList(size-(size/2+1),size);
            var payload=V53DistinctMinorityTest.payload(f,404,"majority-selected");var entry=V53DistinctMinorityTest.entry(f,payload,"DATA");
            Files.write(raw.resolve("entry.gsr"),entry.bytes());Files.write(raw.resolve("payload.bin"),payload);
            V53DistinctMinorityTest.vote(f,all,entry,payload,"initial-vote");f.snapshot("initial-votes");
            if(!phase.equals("ACCEPT")) {
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(all.getFirst().replicaDirectory().resolve("pending.accept")));
                var accepts=new HashSet<>(f.observations);var fields=new TreeMap<>(vote.accept().value());
                fields.put("accepts",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"ACCEPT",vote.accept(),accepts));
                var proof=decode(encode("records","PROOF",fields),"records","PROOF");var proofs=new HashSet<Owned>();
                for(var t:all)try(var owner=f.open(t,"original-proof")){proofs.add(owner.proveCurrent(proof,accepts));}
                f.observations.addAll(proofs);f.snapshot("original-proved");
                if(phase.equals("CERTIFICATE")) {
                    fields=new TreeMap<>(proof.value());fields.put("proofs",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),"PROOF",proof,proofs));
                    var certificate=decode(encode("records","CERTIFICATE",fields),"records","CERTIFICATE");
                    for(var t:all)try(var owner=f.open(t,"original-certificate")){owner.certifyCurrent(certificate,f.observations);}
                    f.snapshot("original-certified");
                }else assertEquals("PROOF",phase);
            }
            var carried=V53DistinctMinorityTest.campaign(f,3,all);
            var copies=new ArrayList<MembershipFloor.Copy>();
            for(var t:all)try(var owner=f.open(t,"retain-context")){owner.retainPendingContext();copies.add(owner.contextFloorCopy());}
            f.snapshot("contexts");
            for(var t:all)try(var owner=f.open(t,"context-retirement")) {
                var quorum=new ArrayList<MembershipFloor.Copy>();quorum.add(copies.stream().filter(c->c.owner.equals(t.identity())).findFirst().orElseThrow());
                copies.stream().filter(c->!c.owner.equals(t.identity())).limit(size/2).forEach(quorum::add);
                owner.establishContextFloor(quorum);owner.retireContextOriginal();owner.retireSource(carried.obsolete().get(t.identity().nodeId().value()));
            }
            f.snapshot("original-retired");return new Original(f,entry,payload);
        }finally{V53CoveredPhasedVoteTest.save(f);}
    }
    Prepared prepared(int size,boolean backup,String phase)throws Exception {
        var original=original(size,backup,phase);var f=original.f();var entry=original.entry();var payload=original.payload();
        var all=f.request.targets();var majority=all.subList(size-(size/2+1),size);
        try {
            for(var t:majority)try(var owner=f.open(t,"majority-reaccept")){f.observations.add(owner.acceptRetainedCurrent(entry,payload));}
            f.snapshot("majority-reaccepted");V53DistinctMinorityTest.publish(f,1,entry,payload,majority);
            var advanced=V53DistinctMinorityTest.campaign(f,4,all,false);f.snapshot("advanced-selected");
            return new Prepared(f,advanced);
        }finally{V53CoveredPhasedVoteTest.save(f);}
    }
    static void install(Prepared p,MembershipGrantJournal owner)throws Exception {owner.installCurrent(p.installation().sources(),List.of(),p.installation().images());}
    static MembershipGrantJournal open(Prepared p,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=p.f();var t=f.request.targets().getFirst();
        return MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),resources,
                (r,packet,images)->MembershipCapsule.verify(r,packet,images,f.observations),MembershipGrantJournal.MAXIMUM,e->{V53RetirementImagesTest.bounded(resources);cut.at(e);});
    }
    static void complete(Prepared p)throws Exception {
        var f=p.f();var all=f.request.targets();
        try {
            for(var t:all)try(var owner=f.open(t,"install-4")){install(p,owner);assertTrue(owner.currentOwnedTail().isEmpty());assertTrue(owner.currentCertificate().isEmpty());}
            f.snapshot("covered-installed");
            for(var t:all.subList(0,all.size()-(all.size()/2+1)))try(var owner=f.open(t,"release-covered-floor")){owner.retireInactive();owner.releaseFloor();}
            f.snapshot("floor-released");V53DistinctMinorityTest.maintain(f,"round-4-settled",all,p.installation().obsolete());
            var next=V53DistinctMinorityTest.campaign(f,5,all);V53DistinctMinorityTest.maintain(f,"round-5-settled",all,next.obsolete());
            var barrier=V53DistinctMinorityTest.entry(f,new byte[0],"BARRIER");Files.write(f.raw.resolve("barrier.gsr"),barrier.bytes());
            V53DistinctMinorityTest.publish(f,2,barrier,new byte[0]);assertEquals(0,f.resources.usage().leases());
        }finally{V53CoveredPhasedVoteTest.save(f);}
    }
    @Test void publishedMajorityCanCoverProtectedOriginalsForEveryInitialProfile()throws Exception {
        Path out=Path.of("target/v53-covered-context-profiles/run-"+UUID.randomUUID());Files.createDirectories(out);var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53CoveredContextProfiles="+out.toAbsolutePath());
        try {
            for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
                var p=prepared(size,backup,"CERTIFICATE");complete(p);String name=size+"-"+(backup?"backup":"empty");
                V53JournalApplicationTest.copy(p.f().raw,out.resolve(name));rows.add(Map.of("case",name,"status","PASS","size",size,"backup",backup));
                System.out.println("v53CoveredContextProfile="+name+" PASS");System.out.flush();
            }
        }finally{Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-context-profiles-v1","status",rows.size()==6?"PASS":"FAIL","cases",rows),65536));}
    }
    @Test void acceptAndProofContextsAlsoCompleteWithoutInventingCertificate()throws Exception {
        for(String phase:List.of("ACCEPT","PROOF")){var p=prepared(3,false,phase);complete(p);}
    }
    @Test void coveredContextRecoversAcrossRepeatedInstallAndCleanupInterruptions()throws Exception {
        var p=prepared(3,false,"CERTIFICATE");var f=p.f();Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed");
        V53JournalApplicationTest.copy(node,seed);var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        for(String point:List.of("INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_WRITTEN","INSTALL_SELECTOR_RENAMED","INSTALL_PARENT_FORCED",
                "CONTEXT_SETTLEMENT_VALIDATED","SETTLED_VOTE_PREFIX_WRITTEN","SETTLED_VOTE_RENAMED","CONTEXT_SETTLEMENT_EMPTY_FORCED",
                "CONTEXT_REDUNDANT_DELETED","CONTEXT_REDUNDANT_PARENT_FORCED","CONTEXT_SETTLEMENT_CLEARED")) {
            Files.move(node,temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);var resources=new MembershipResources(512*MembershipResources.MIB);
            Path raw=Files.createDirectory(f.raw.resolve("interrupted-"+point));var first=new ArrayList<String>();
            assertThrows(IOException.class,()->{try(var owner=open(p,resources,e->{first.add(e);if(e.equals(point))throw new IOException(e);})){install(p,owner);}});
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("first"));
            String retryPoint=point.equals("INSTALL_MANIFEST_FORCED") || point.equals("INSTALL_SELECTOR_WRITTEN")?"CONTEXT_SOURCE_PARENT_FORCED":
                    Files.exists(node.resolve("pending.context"))?"CONTEXT_SETTLEMENT_EMPTY_FORCED":"ACCEPT_ACTIVE_FORCED";
            var second=new ArrayList<String>();assertThrows(IOException.class,()->{try(var owner=open(p,resources,e->{second.add(e);if(e.equals(retryPoint))throw new IOException(e);})){install(p,owner);}});
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("second"));
            var end=new ArrayList<String>();try(var owner=open(p,resources,end::add)){install(p,owner);assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));assertTrue(owner.currentOwnedTail().isEmpty());}
            assertFalse(Files.exists(node.resolve("pending.context")));assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("final"));
            Files.write(raw.resolve("events.json"),canonical(Map.of("first",first,"second",second,"final",end),1024*1024));rows.add(Map.of("cut",point,"secondCut",retryPoint,"status","PASS"));
        }
        Files.write(f.raw.resolve("interruptions.json"),canonical(rows,16384));V53CoveredPhasedVoteTest.save(f);
        System.out.println("v53CoveredContextInterruptions="+f.raw.toAbsolutePath());
    }
    @Test void lostOrChangedCleanupAuthorityNeverErasesTheOriginal()throws Exception {
        var p=prepared(3,false,"CERTIFICATE");Path node=p.f().request.targets().getFirst().replicaDirectory(),seed=temp.resolve("refusal-seed");
        V53JournalApplicationTest.copy(node,seed);int ordinal=0;var results=new ArrayList<Map<String,Object>>();
        for(String kind:List.of("missing-context","context","floor","source","vote","candidate")) {
            Files.move(node,temp.resolve("refusal-before-"+ordinal++));V53JournalApplicationTest.copy(seed,node);var resources=new MembershipResources(512*MembershipResources.MIB);
            String point=kind.equals("candidate")?"SETTLED_VOTE_PREFIX_WRITTEN":"CONTEXT_SETTLEMENT_VALIDATED";
            assertThrows(IOException.class,()->{try(var owner=open(p,resources,event->{if(event.equals(point))throw new IOException(event);})){install(p,owner);}});
            Path repair=temp.resolve("refusal-repair-"+kind);V53JournalApplicationTest.copy(node,repair);
            Path file=kind.equals("floor")?node.resolve("floor-copies/floor.gsr"):kind.equals("vote")?node.resolve("pending.accept"):
                    kind.equals("candidate")?node.resolve("pending.accept.next"):node.resolve("pending.context");
            if(kind.equals("source")) {
                var context=MembershipPendingContext.backingBasis(MembershipPendingContext.decode(Files.readAllBytes(node.resolve("pending.context"))));
                file=node.resolve("sources/"+context.value().get("basisId")+"/source.gscp");
            }
            if(kind.equals("missing-context"))Files.delete(file);else {var bytes=Files.readAllBytes(file);bytes[bytes.length-1]^=1;Files.write(file,bytes);}
            var before=V53ReplayFilesTest.files(node);String reason=null;
            for(int i=0;i<2;i++) {
                var failure=assertThrows(IllegalArgumentException.class,()->{try(var owner=open(p,resources,event->{})) {}});
                if(reason!=null)assertEquals(reason,failure.getMessage());reason=failure.getMessage();
                assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
            }
            Files.move(node,temp.resolve("refused-"+kind));V53JournalApplicationTest.copy(repair,node);
            try(var owner=open(p,resources,event->{})){install(p,owner);assertTrue(owner.currentOwnedTail().isEmpty());}
            assertEquals(0,resources.usage().leases());results.add(Map.of("case",kind,"reason",reason,"status","PASS"));
        }
        Files.write(p.f().raw.resolve("refusals.json"),canonical(results,16384));
        System.out.println("v53CoveredContextRefusals="+p.f().raw.toAbsolutePath());
    }
    @Test void higherVolatileObservationAllowsCleanupButNeverAnOldInstallationReceipt()throws Exception {
        var p=prepared(3,false,"CERTIFICATE");var resources=new MembershipResources(512*MembershipResources.MIB);
        var live=new java.util.concurrent.atomic.AtomicReference<MembershipGrantJournal>();var trace=new ArrayList<String>();
        try(var owner=open(p,resources,event->{
            trace.add(event);if(event.equals("CONTEXT_SETTLEMENT_VALIDATED")) {
                var higher=new TreeMap<>(p.f().ballot);higher.put("counter",9L);live.get().observeCurrent(higher);
            }
        })) {
            live.set(owner);var failure=assertThrows(IllegalArgumentException.class,()->install(p,owner));
            assertEquals("higher ballot observed; fresh campaign required",failure.getMessage());
        }
        Path node=p.f().request.targets().getFirst().replicaDirectory();assertFalse(Files.exists(node.resolve("pending.context")));
        assertNull(MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept"))));assertEquals(0,resources.usage().leases());
        assertTrue(trace.contains("CONTEXT_SETTLEMENT_CLEARED"));
        try(var owner=open(p,resources,event->{})){install(p,owner);assertTrue(owner.currentCertificate().isEmpty());}
        assertEquals(0,resources.usage().leases());
    }
}
