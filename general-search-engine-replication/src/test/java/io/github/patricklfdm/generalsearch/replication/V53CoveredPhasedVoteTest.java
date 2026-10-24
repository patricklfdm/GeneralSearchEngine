package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Actual phased originals on a lagging owner; only the disjoint majority applies. */
class V53CoveredPhasedVoteTest {
    @TempDir Path temp;
    record Prepared(V53BootstrapPublicationTest.Fixture f,V53DistinctMinorityTest.Installation installation,String phase) {}
    @FunctionalInterface interface BeforeCampaign {void run(V53BootstrapPublicationTest.Fixture fixture)throws Exception;}
    Prepared prepared(int size,boolean backup,String phase)throws Exception {return prepared(size,backup,phase,f->{});}
    Prepared prepared(int size,boolean backup,String phase,BeforeCampaign beforeCampaign)throws Exception {
        Path raw=Path.of("target/v53-covered-phased-vote/run-"+UUID.randomUUID());Files.createDirectories(raw);
        System.out.println("v53CoveredPhasedVoteEvidence="+raw.toAbsolutePath());
        Files.write(raw.resolve("profile.json"),canonical(Map.of("size",size,"backup",backup,"phase",phase),16384));
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve("fixture-"+UUID.randomUUID())),raw,size,backup);f.campaign(1);
        var all=f.request.targets();var lagging=all.subList(0,size-(size/2+1));var majority=all.subList(lagging.size(),size);
        byte[] payload=V53DistinctMinorityTest.payload(f,404,"majority-selected");var entry=V53DistinctMinorityTest.entry(f,payload,"DATA");
        Files.write(raw.resolve("entry.gsr"),entry.bytes());Files.write(raw.resolve("payload.bin"),payload);
        V53DistinctMinorityTest.vote(f,all,entry,payload,"initial-vote");f.snapshot("initial-votes");
        V53DistinctMinorityTest.publish(f,1,entry,payload,majority);
        String donor=majority.getFirst().identity().nodeId().value();
        var original=MembershipPendingAccept.decode(Files.readAllBytes(raw.resolve("slot-1-certified/"+donor+"/pending.accept")));
        var accepted=f.observations.stream().filter(o->o.record().equals(original.accept().digest())).collect(java.util.stream.Collectors.toSet());
        for(var target:lagging)try(var owner=f.open(target,"lagging-proof")) {
            var ack=owner.proveCurrent(original.proof(),accepted);assertEquals(ack,owner.proveCurrent(original.proof(),accepted));f.observations.add(ack);
        }
        f.snapshot("lagging-proved");
        if(phase.equals("CERTIFICATE")) {
            var phased=f.observations.stream().filter(o->o.record().equals(original.accept().digest()) || o.record().equals(original.proof().digest())).collect(java.util.stream.Collectors.toSet());
            for(var target:lagging)try(var owner=f.open(target,"lagging-certificate")) {
                assertArrayEquals(original.certificate().bytes(),owner.certifyCurrent(original.certificate(),phased).bytes());
                assertArrayEquals(original.certificate().bytes(),owner.certifyCurrent(original.certificate(),phased).bytes());
            }
            f.snapshot("lagging-certified");
        }else assertEquals("PROOF",phase);
        beforeCampaign.run(f);var installation=V53DistinctMinorityTest.campaign(f,3,all,false);f.snapshot("before-install");
        save(f);return new Prepared(f,installation,phase);
    }
    static void save(V53BootstrapPublicationTest.Fixture f)throws Exception {
        Files.write(f.raw.resolve("calls.json"),canonical(f.calls,8*1024*1024));
        Files.write(f.raw.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
    }
    void complete(Prepared p)throws Exception {
        var f=p.f();var all=f.request.targets();
        try {
            for(var target:all)try(var owner=f.open(target,"install-3")) {
                owner.installCurrent(p.installation().sources(),List.of(),p.installation().images());
                assertTrue(owner.currentOwnedTail().isEmpty());assertTrue(owner.currentOwnedProof().isEmpty());assertTrue(owner.currentCertificate().isEmpty());
            }
            f.snapshot("round-3-installed");V53DistinctMinorityTest.maintain(f,"round-3-settled",all,p.installation().obsolete());
            var later=V53DistinctMinorityTest.campaign(f,4,all);V53DistinctMinorityTest.maintain(f,"round-4-settled",all,later.obsolete());
            var barrier=V53DistinctMinorityTest.entry(f,new byte[0],"BARRIER");Files.write(f.raw.resolve("barrier.gsr"),barrier.bytes());
            V53DistinctMinorityTest.publish(f,2,barrier,new byte[0]);assertEquals(0,f.resources.usage().leases());
        }finally{save(f);}
    }
    @Test void proofAndCertificateLaggingVotersRecoverForAllInitialProfiles()throws Exception {
        Path evidence=Path.of("target/v53-covered-phased-profiles/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53CoveredPhasedProfilesEvidence="+evidence.toAbsolutePath());
        try {
            for(String phase:List.of("PROOF","CERTIFICATE"))for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
                var p=prepared(size,backup,phase);String name=phase+"-"+size+"-"+(backup?"backup":"empty");complete(p);
                V53JournalApplicationTest.copy(p.f().raw,evidence.resolve(name));rows.add(Map.of("case",name,"phase",phase,"size",size,"backup",backup,"status","PASS"));
                System.out.println("v53CoveredPhasedProfile="+name+" PASS");System.out.flush();
            }
        }finally {
            Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-phased-profiles-v1","status",rows.size()==12?"PASS":"FAIL","cases",rows,"publicBootstrap",true,"runtimeEnabled",false),65536));
        }
        assertEquals(12,rows.size());
    }
    MembershipGrantJournal open(Prepared p,MembershipResources resources,MembershipBallotAllocator.Cut cut)throws Exception {
        var f=p.f();var t=f.request.targets().getFirst();return MembershipGrantJournal.openBootstrapped(t.replicaDirectory(),t.materialization().directory(),f.result.root(),t.identity(),resources,
                (r,packet,images)->MembershipCapsule.verify(r,packet,images,f.observations),MembershipGrantJournal.MAXIMUM,e->{V53RetirementImagesTest.bounded(resources);cut.at(e);});
    }
    void install(Prepared p,MembershipGrantJournal owner)throws Exception {owner.installCurrent(p.installation().sources(),List.of(),p.installation().images());}
    @Test void repeatedInterruptionPreservesEveryPhasedOriginalUntilForcedSelectorAndCleanup()throws Exception {
        for(String phase:List.of("PROOF","CERTIFICATE")) {
            var p=prepared(3,false,phase);var f=p.f();var node=f.request.targets().getFirst().replicaDirectory();Path seed=temp.resolve("seed-"+phase);V53JournalApplicationTest.copy(node,seed);
            var original=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));var source=p.installation().sources().getFirst();
            assertNotNull(original.proof());assertEquals(phase.equals("CERTIFICATE"),original.certificate()!=null);var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
            for(String point:List.of("INSTALL_MANIFEST_FORCED","INSTALL_SELECTOR_RENAMED","INSTALL_SELECTOR_FORCED","SETTLED_VOTE_VALIDATED",
                    "SETTLED_VOTE_CANDIDATE_CREATED","SETTLED_VOTE_PREFIX_WRITTEN","SETTLED_VOTE_CANDIDATE_WRITTEN","SETTLED_VOTE_CANDIDATE_FORCED",
                    "SETTLED_VOTE_CANDIDATE_PARENT_FORCED","SETTLED_VOTE_RENAMED","SETTLED_VOTE_PARENT_FORCED","SETTLED_VOTE_BEFORE_RETURN")) {
                Files.move(node,temp.resolve("previous-"+phase+"-"+ordinal++));V53JournalApplicationTest.copy(seed,node);var resources=new MembershipResources(512*MembershipResources.MIB);var events=new ArrayList<String>();
                assertThrows(java.io.IOException.class,()->{try(var owner=open(p,resources,e->{events.add(e);if(e.equals(point))throw new java.io.IOException(e);})){install(p,owner);}});
                assertEquals(0,resources.usage().leases());Path raw=Files.createDirectory(f.raw.resolve("interrupted-"+point));V53JournalApplicationTest.copy(node,raw.resolve("first"));
                String second=point.equals("INSTALL_MANIFEST_FORCED")?phase+"_ACTIVE_FORCED":Set.of("SETTLED_VOTE_RENAMED","SETTLED_VOTE_PARENT_FORCED","SETTLED_VOTE_BEFORE_RETURN").contains(point)?"ACCEPT_ACTIVE_FORCED":"SETTLED_VOTE_CANDIDATE_PARENT_FORCED";
                var recovery=new ArrayList<String>();assertThrows(java.io.IOException.class,()->{try(var owner=open(p,resources,e->{recovery.add(e);if(e.equals(second))throw new java.io.IOException(e);})){install(p,owner);}});
                assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("second"));
                var completed=new ArrayList<String>();try(var owner=open(p,resources,completed::add)) {
                    install(p,owner);assertTrue(owner.currentOwnedTail().isEmpty());assertTrue(owner.currentOwnedProof().isEmpty());assertTrue(owner.currentCertificate().isEmpty());
                    assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));
                }
                assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("final"));
                assertArrayEquals(source.capsule.packet.bytes(),Files.readAllBytes(node.resolve("sources/"+source.basis.value().get("basisId")+"/source.gscp")));
                assertArrayEquals(original.proof().bytes(),source.capsule.packet.objectBytes(original.proof().digest()));
                if(original.certificate()!=null)assertArrayEquals(original.certificate().bytes(),source.capsule.packet.objectBytes(original.certificate().digest()));
                Files.write(raw.resolve("events.json"),canonical(Map.of("first",events,"second",recovery,"final",completed),1024*1024));rows.add(Map.of("cut",point,"second",second,"status","PASS"));
            }
            Files.write(f.raw.resolve("interruptions.json"),canonical(rows,65536));save(f);
        }
    }
    @Test void anotherValidWitnessSetCannotReplaceThePinnedOriginalPhase()throws Exception {
        for(String phase:List.of("PROOF","CERTIFICATE")) {
            var p=prepared(3,false,phase);var f=p.f();var node=f.request.targets().getFirst().replicaDirectory();var resources=new MembershipResources(512*MembershipResources.MIB);
            assertThrows(java.io.IOException.class,()->{try(var owner=open(p,resources,e->{if(e.equals("SETTLED_VOTE_VALIDATED"))throw new java.io.IOException("stop");})){install(p,owner);}});
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,f.raw.resolve("before-damage"));
            var original=MembershipPendingAccept.decode(Files.readAllBytes(node.resolve("pending.accept")));var fields=new TreeMap<>(phase.equals("PROOF")?original.proof().value():original.certificate().value());
            var selector=decode(Files.readAllBytes(node.resolve("selector.gsr")),"records","SELECTOR");
            assertFalse(Arrays.equals(selector.bytes(),original.selector().bytes()));
            var generation=decode(Files.readAllBytes(node.resolve("generations/"+selector.value().get("generation")+"/generation.gsr")),"records","GENERATION");
            assertEquals(1L,object(generation.value().get("cut")).get("index"));
            var witnessRecord=phase.equals("PROOF")?original.accept():original.proof();var owned=f.observations.stream().filter(o->o.record().equals(witnessRecord.digest())).collect(java.util.stream.Collectors.toSet());
            assertEquals(3,owned.size());fields.put(phase.equals("PROOF")?"accepts":"proofs",V53PublicationLifetimeTest.witnesses(f.result.root().manifestDigest(),phase.equals("PROOF")?"ACCEPT":"PROOF",witnessRecord,owned));
            var changed=decode(encode("records",phase,fields),"records",phase);var vote=phase.equals("PROOF")?original.withProof(changed):original.withCertificate(changed);
            assertFalse(Arrays.equals(vote.bytes(),original.bytes()));Files.write(node.resolve("pending.accept"),vote.bytes());var before=V53ReplayFilesTest.files(node);
            for(int attempt=0;attempt<2;attempt++) {
                var error=assertThrows(IllegalArgumentException.class,()->{try(var ignored=open(p,resources,e->{})){fail("altered original phase accepted");}});
                assertEquals("settlement source changed original vote",error.getMessage());assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
            }
            V53JournalApplicationTest.copy(node,f.raw.resolve("refused"));save(f);
        }
    }
}
