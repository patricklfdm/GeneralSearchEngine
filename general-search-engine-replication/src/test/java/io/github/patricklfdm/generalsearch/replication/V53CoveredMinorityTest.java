package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53CoveredMinorityTest {
    @TempDir Path temp;
    record Prepared(V53BootstrapPublicationTest.Fixture f,V53DistinctMinorityTest.Installation installation) {}
    Prepared prepared()throws Exception {
        Path raw=Path.of("target/v53-covered-minority/run-"+UUID.randomUUID());Files.createDirectories(raw);
        System.out.println("v53CoveredMinorityEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(temp,raw,3,false);f.campaign(1);
        var all=f.request.targets();var minority=all.subList(0,1);var majority=all.subList(1,3);
        byte[] losing=V53DistinctMinorityTest.payload(f,403,"minority-original");var old=V53DistinctMinorityTest.entry(f,losing,"DATA");
        Files.write(raw.resolve("minority-entry.gsr"),old.bytes());Files.write(raw.resolve("minority-payload.bin"),losing);
        V53DistinctMinorityTest.vote(f,minority,old,losing,"minority-vote");f.snapshot("minority-accepted");
        var setup=V53DistinctMinorityTest.campaign(f,3,majority);V53DistinctMinorityTest.maintain(f,"round-3-settled",majority,setup.obsolete());
        byte[] chosen=V53DistinctMinorityTest.payload(f,404,"majority-selected");var entry=V53DistinctMinorityTest.entry(f,chosen,"DATA");
        Files.write(raw.resolve("selected-entry.gsr"),entry.bytes());Files.write(raw.resolve("selected-payload.bin"),chosen);
        V53DistinctMinorityTest.publish(f,1,entry,chosen,majority);
        var installation=V53DistinctMinorityTest.campaign(f,4,all,false);f.snapshot("before-install");return new Prepared(f,installation);
    }
    @Test void authenticatedPublishedPrefixSettlesAnUnprovenMinorityVote()throws Exception {
        var p=prepared();var f=p.f();var raw=f.raw;var all=f.request.targets();var installed=p.installation();
        try {
            for(var t:all)try(var owner=f.open(t,"install-4")){owner.installCurrent(installed.sources(),List.of(),installed.images());}
            f.snapshot("round-4-installed");
            for(var t:all)try(var owner=f.open(t,"inspect-settlement")) {
                assertTrue(owner.currentOwnedTail().isEmpty());assertTrue(owner.currentCertificate().isEmpty());
                assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
            }
            V53DistinctMinorityTest.maintain(f,"round-4-settled",all,installed.obsolete());
            var later=V53DistinctMinorityTest.campaign(f,5,all);V53DistinctMinorityTest.maintain(f,"round-5-settled",all,later.obsolete());
            var barrier=V53DistinctMinorityTest.entry(f,new byte[0],"BARRIER");Files.write(raw.resolve("barrier.gsr"),barrier.bytes());
            V53DistinctMinorityTest.publish(f,2,barrier,new byte[0]);assertEquals(0,f.resources.usage().leases());
        }finally {
            Files.write(raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
            Files.write(raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        }
    }
    MembershipGrantJournal open(Prepared p,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=p.f();var t=f.request.targets().getFirst();return MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),resources,
                (r,packet,images)->MembershipCapsule.verify(r,packet,images,f.observations),MembershipGrantJournal.MAXIMUM,e->{V53RetirementImagesTest.bounded(resources);cut.at(e);});
    }
    void install(Prepared p,MembershipGrantJournal owner)throws Exception {owner.installCurrent(p.installation().sources(),List.of(),p.installation().images());}
    void reset(Prepared p,Path seed,String label)throws Exception {
        var node=p.f().request.targets().getFirst().replicaDirectory();Files.move(node,temp.resolve(label));V53JournalApplicationTest.copy(seed,node);
    }
    @Test void repeatedInterruptionKeepsOriginalsUntilForcedReplacementAndReopensExactly()throws Exception {
        var p=prepared();var f=p.f();var node=f.request.targets().getFirst().replicaDirectory();var seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);
        var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        for(String point:List.of("INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_RENAMED","INSTALL_SELECTOR_FORCED","SETTLED_VOTE_VALIDATED",
                "SETTLED_VOTE_CANDIDATE_CREATED","SETTLED_VOTE_PREFIX_WRITTEN","SETTLED_VOTE_CANDIDATE_WRITTEN","SETTLED_VOTE_CANDIDATE_FORCED",
                "SETTLED_VOTE_CANDIDATE_PARENT_FORCED","SETTLED_VOTE_RENAMED","SETTLED_VOTE_PARENT_FORCED","SETTLED_VOTE_BEFORE_RETURN")) {
            reset(p,seed,"previous-"+(ordinal++));var resources=new MembershipResources(512*MembershipResources.MIB);var events=new ArrayList<String>();
            assertThrows(java.io.IOException.class,()->{try(var owner=open(p,resources,e->{events.add(e);if(e.equals(point))throw new java.io.IOException(e);})){install(p,owner);}});
            assertEquals(0,resources.usage().leases());Path out=Files.createDirectory(f.raw.resolve("interrupted-"+point));V53JournalApplicationTest.copy(node,out.resolve("first"));
            String second=point.equals("INSTALL_MANIFEST_FORCED") || point.equals("SETTLED_VOTE_RENAMED") || point.equals("SETTLED_VOTE_PARENT_FORCED") || point.equals("SETTLED_VOTE_BEFORE_RETURN")?"ACCEPT_ACTIVE_FORCED":"SETTLED_VOTE_CANDIDATE_PARENT_FORCED";
            var recovery=new ArrayList<String>();assertThrows(java.io.IOException.class,()->{try(var owner=open(p,resources,e->{recovery.add(e);if(e.equals(second))throw new java.io.IOException(e);})){install(p,owner);}});
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,out.resolve("second"));
            var completed=new ArrayList<String>();try(var owner=open(p,resources,completed::add)) {
                install(p,owner);assertTrue(owner.currentOwnedTail().isEmpty());assertTrue(owner.currentCertificate().isEmpty());assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
            }
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,out.resolve("final"));
            // The selected local original source still contains the losing ACCEPT.
            var source=p.installation().sources().getFirst();assertNotNull(source.basis.value().get("accepted"));
            assertArrayEquals(source.capsule.packet.bytes(),Files.readAllBytes(node.resolve("sources/"+source.basis.value().get("basisId")+"/source.gscp")));
            Files.write(out.resolve("events.json"),canonical(Map.of("first",events,"second",recovery,"final",completed),1024*1024));
            rows.add(Map.of("cut",point,"second",second,"status","PASS"));
        }
        Files.write(f.raw.resolve("interruptions.json"),canonical(rows,65536));
        Files.write(f.raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
    }
    @Test void damagedOriginalsAndAnUnrelatedEmptyCandidateDoNotAuthorizeCleanup()throws Exception {
        var p=prepared();var node=p.f().request.targets().getFirst().replicaDirectory();var resources=new MembershipResources(512*MembershipResources.MIB);
        assertThrows(java.io.IOException.class,()->{try(var owner=open(p,resources,e->{if(e.equals("SETTLED_VOTE_VALIDATED"))throw new java.io.IOException(e);})){install(p,owner);}});
        var seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);int ordinal=0;
        for(String damage:List.of("old-generation","source","proof","candidate")) {
            reset(p,seed,"previous-"+(ordinal++));var vote=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));
            if(damage.equals("old-generation"))Files.delete(node.resolve("generations/"+vote.selector().value().get("generation")+"/selected.gsr"));
            else if(damage.equals("source"))Files.writeString(node.resolve("sources/"+p.installation().sources().getFirst().basis.value().get("basisId")+"/source.gscp"),"changed");
            else if(damage.equals("proof")) {
                // Syntactically valid forged proof, solely a rejection fixture: no
                // fabricated observation is ever passed to a positive owner call.
                var witnesses=new ArrayList<Map<String,Object>>();for(var t:p.f().request.targets().subList(0,2))
                    witnesses.add(Map.of("voter",t.identity().nodeId().value(),"incarnation",t.identity().storageId().toString(),"receipt","0".repeat(64)));
                var fields=new TreeMap<>(vote.accept().value());fields.put("accepts",witnesses);
                Files.write(node.resolve("pending.accept"),vote.withProof(decode(encode("records","PROOF",fields),"records","PROOF")).bytes());
            }else Files.write(node.resolve("pending.accept.next"),vote.bytes());
            var before=V53ReplayFilesTest.files(node);for(int repeat=0;repeat<2;repeat++) {
                var rejected=assertThrows(IllegalArgumentException.class,()->{try(var ignored=open(p,resources,e->{})){fail("damaged settlement accepted");}});
                if(damage.equals("proof"))assertEquals("settlement requires bare original ACCEPT",rejected.getMessage());
                assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
            }
        }
    }
    @Test void laterObservationDoesNotStopCleanupButRejectsTheOldInstallationResponse()throws Exception {
        var p=prepared();var resources=new MembershipResources(512*MembershipResources.MIB);var holder=new MembershipGrantJournal[1];var higher=new TreeMap<>(p.f().ballot);higher.put("counter",5L);
        var error=assertThrows(IllegalArgumentException.class,()->{try(var owner=open(p,resources,e->{if(e.equals("SETTLED_VOTE_CANDIDATE_FORCED"))holder[0].observeCurrent(higher);})) {holder[0]=owner;install(p,owner);}});
        assertEquals("higher ballot observed; fresh campaign required",error.getMessage());assertEquals(0,resources.usage().leases());
        try(var owner=open(p,resources,e->{})){assertTrue(owner.currentOwnedTail().isEmpty());assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));}
        assertEquals(0,resources.usage().leases());
    }
}
