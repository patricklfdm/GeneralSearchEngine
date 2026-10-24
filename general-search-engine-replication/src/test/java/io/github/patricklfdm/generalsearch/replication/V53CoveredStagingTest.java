package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** A published majority covers a lagging owner's actual applied certificate. */
class V53CoveredStagingTest {
    @TempDir Path temp;
    static final List<String> CUTS=List.of("STAGED_RETIREMENT_AUTHORITY_VALIDATED","REPLAY_CLAIM_PREFIX_WRITTEN","REPLAY_APPLICATION_FINISHED",
            "SUPERSEDED_END_VALIDATED","SUPERSEDED_END_RETIREMENT_CREATED","SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN",
            "SUPERSEDED_END_RETIREMENT_WRITTEN","SUPERSEDED_END_RETIREMENT_FORCED","SUPERSEDED_END_RETIREMENT_PARENT_FORCED",
            "SUPERSEDED_END_RETIREMENT_RENAMED","SUPERSEDED_END_AUTHORITY_FORCED","SUPERSEDED_END_BEFORE_DELETE","SUPERSEDED_END_FILE_DELETED",
            "SUPERSEDED_END_BEFORE_RETIREMENT_DELETE","SUPERSEDED_END_RETIREMENT_DELETED","SUPERSEDED_END_BEFORE_DIRECTORY_DELETE",
            "SUPERSEDED_END_DIRECTORY_DELETED","STAGED_RETIREMENT_BEFORE_RETURN");
    V53CoveredPhasedVoteTest helper()throws Exception {var h=new V53CoveredPhasedVoteTest();h.temp=Files.createDirectory(temp.resolve("producer-"+UUID.randomUUID()));return h;}
    static Set<MembershipContext.Owned> phased(V53CoveredPhasedVoteTest.Prepared p)throws Exception {
        var target=p.f().request.targets().getFirst();var vote=MembershipPendingAccept.decode(Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
        return p.f().observations.stream().filter(o->o.record().equals(vote.accept().digest()) || o.record().equals(vote.proof().digest())).collect(java.util.stream.Collectors.toSet());
    }
    V53CoveredPhasedVoteTest.Prepared prepared(V53CoveredPhasedVoteTest helper,int size,boolean backup)throws Exception {
        return helper.prepared(size,backup,"CERTIFICATE",f->{
            for(var target:f.request.targets().subList(0,size-(size/2+1))) {
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
                var phased=f.observations.stream().filter(o->o.record().equals(vote.accept().digest()) || o.record().equals(vote.proof().digest())).collect(java.util.stream.Collectors.toSet());
                try(var owner=f.open(target,"lagging-apply")) {
                    var applied=owner.applyCurrent(builder().configuration(),target.materialization(),phased);f.observations.add(applied.endorsement().owned());
                    applied.endorsement().parent().ifPresent(parent->f.observations.add(parent.owned()));
                    for(var parent:applied.endorsement().ancestors())f.observations.add(parent.owned());
                    assertTrue(owner.currentCertificate().isPresent());
                }
            }
            f.snapshot("lagging-applied");
        });
    }
    static void retire(V53CoveredPhasedVoteTest.Prepared p,MembershipGrantJournal owner,int node)throws Exception {
        owner.retireCoveredApplication(builder().configuration(),p.f().request.targets().get(node).materialization(),phased(p),
                p.installation().sources(),List.of(),List.of(),p.installation().images());
    }
    @Test void actualAppliedButUnpublishedVotersRecoverForAllInitialProfiles()throws Exception {
        Path out=Path.of("target/v53-covered-staging-profiles/run-"+UUID.randomUUID());Files.createDirectories(out);var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53CoveredStagingProfilesEvidence="+out.toAbsolutePath());
        try {
            for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
                var helper=helper();var p=prepared(helper,size,backup);var f=p.f();
                for(int i=0;i<size-(size/2+1);i++) {
                    var target=f.request.targets().get(i);var before=V53ReplayFilesTest.files(target.replicaDirectory());
                    try(var owner=f.open(target,"retire-covered-application")) {
                        var original=owner.currentCertificate().orElseThrow();
                        retire(p,owner,i);retire(p,owner,i);
                        assertArrayEquals(original.bytes(),owner.currentCertificate().orElseThrow().bytes());V53StagedApplicationTest.noStaging(target.replicaDirectory());
                    }
                    var after=V53ReplayFilesTest.files(target.replicaDirectory());
                    before.keySet().removeIf(n->n.equals("applied-end") || n.startsWith("applied-end/"));assertEquals(before,after);
                }
                f.snapshot("staging-retired");helper.complete(p);String name=size+"-"+(backup?"backup":"empty");V53JournalApplicationTest.copy(f.raw,out.resolve(name));
                rows.add(Map.of("case",name,"size",size,"backup",backup,"status","PASS"));System.out.println("v53CoveredStagingProfile="+name+" PASS");
            }
        }finally {Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-staging-profiles-v1","status",rows.size()==6?"PASS":"FAIL","cases",rows,"runtimeEnabled",false),65536));}
        assertEquals(6,rows.size());
    }
    @Test void repeatedInterruptionRetainsEveryOriginalAndRequiresTheSameCleanupAuthority()throws Exception {
        var helper=helper();var p=prepared(helper,3,false);var f=p.f();Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);
        var original=V53ReplayFilesTest.files(node);var rows=new ArrayList<Map<String,Object>>();int ordinal=0;
        System.out.println("v53CoveredStagingInterruptionsEvidence="+f.raw.toAbsolutePath());
        for(String point:CUTS) {
            Files.move(node,temp.resolve("previous-"+ordinal++));V53JournalApplicationTest.copy(seed,node);var resources=new MembershipResources(512*MembershipResources.MIB);var events=new ArrayList<String>();
            assertThrows(IOException.class,()->{try(var owner=helper.open(p,resources,e->{events.add(e);if(e.equals(point))throw new IOException(e);})){retire(p,owner,0);}});
            assertEquals(0,resources.usage().leases());Path raw=Files.createDirectory(f.raw.resolve("interrupted-"+point));V53JournalApplicationTest.copy(node,raw.resolve("first"));
            String second=point.equals("STAGED_RETIREMENT_BEFORE_RETURN") || point.equals("SUPERSEDED_END_DIRECTORY_DELETED")?"CERTIFICATE_ACTIVE_FORCED":"SUPERSEDED_END_AUTHORITY_FORCED";
            var recovery=new ArrayList<String>();assertThrows(IOException.class,()->{try(var owner=helper.open(p,resources,e->{recovery.add(e);if(e.equals(second))throw new IOException(e);})){retire(p,owner,0);}});
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("second"));
            var completed=new ArrayList<String>();try(var owner=helper.open(p,resources,completed::add)) {retire(p,owner,0);V53StagedApplicationTest.noStaging(node);assertTrue(owner.currentCertificate().isPresent());}
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("final"));var expected=new TreeMap<>(original);expected.keySet().removeIf(n->n.equals("applied-end") || n.startsWith("applied-end/"));assertEquals(expected,V53ReplayFilesTest.files(node));
            try(var owner=helper.open(p,resources,e->{})){helper.install(p,owner);assertTrue(owner.currentCertificate().isEmpty());assertEquals(1L,owner.floorCopyCurrent().capsule.context.cut.get("index"));}
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("installed"));
            Files.write(raw.resolve("events.json"),canonical(Map.of("first",events,"second",recovery,"final",completed),1024*1024));rows.add(Map.of("cut",point,"second",second,"status","PASS"));
        }
        Files.write(f.raw.resolve("interruptions.json"),canonical(rows,65536));V53CoveredPhasedVoteTest.save(f);
    }
    @Test void changedImagesMissingObservationsAndChangedDerivedEndCannotAuthorizeDeletion()throws Exception {
        var helper=helper();var p=prepared(helper,3,false);var f=p.f();var t=f.request.targets().getFirst();Path node=t.replicaDirectory();var resources=new MembershipResources(512*MembershipResources.MIB);
        var before=V53ReplayFilesTest.files(node);var wrong=new TreeMap<>(p.installation().images());var h=wrong.firstKey();var bytes=wrong.get(h).clone();bytes[bytes.length-1]^=1;wrong.put(h,bytes);
        try(var owner=helper.open(p,resources,e->{})) {
            assertThrows(IllegalArgumentException.class,()->owner.retireCoveredApplication(builder().configuration(),t.materialization(),Set.of(),p.installation().sources(),List.of(),List.of(),p.installation().images()));
            assertEquals(before,V53ReplayFilesTest.files(node));
            assertThrows(IllegalArgumentException.class,()->owner.retireCoveredApplication(builder().configuration(),t.materialization(),phased(p),p.installation().sources(),List.of(),List.of(),wrong));
            assertEquals(before,V53ReplayFilesTest.files(node));
        }
        assertEquals(0,resources.usage().leases());Path ack=node.resolve("applied-end/ack.gsr");var saved=Files.readAllBytes(ack);var altered=saved.clone();altered[altered.length-1]^=1;Files.write(ack,altered);
        var damaged=V53ReplayFilesTest.files(node);
        for(int i=0;i<2;i++) {assertThrows(IllegalArgumentException.class,()->{try(var owner=helper.open(p,resources,e->{})){retire(p,owner,0);}});assertEquals(damaged,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());}
        Files.write(ack,saved);try(var owner=helper.open(p,resources,e->{})){retire(p,owner,0);helper.install(p,owner);}assertEquals(0,resources.usage().leases());
    }
    @Test void newerVolatileObservationAllowsOnlyExactDerivedCleanupAndFencesInstallation()throws Exception {
        var helper=helper();var p=prepared(helper,3,false);var f=p.f();Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("observed-seed");V53JournalApplicationTest.copy(node,seed);
        var vote=Files.readAllBytes(node.resolve("pending.accept"));var journal=Files.readAllBytes(node.resolve("grants.gsr"));var resources=new MembershipResources(512*MembershipResources.MIB);int n=0;
        for(String cut:List.of("before","STAGED_RETIREMENT_AUTHORITY_VALIDATED","SUPERSEDED_END_AUTHORITY_FORCED","SUPERSEDED_END_FILE_DELETED","STAGED_RETIREMENT_BEFORE_RETURN")) {
            Files.move(node,temp.resolve("observed-previous-"+n++));V53JournalApplicationTest.copy(seed,node);MembershipGrantJournal[] active={null};boolean[] seen={false};
            try(var owner=helper.open(p,resources,event->{if(event.equals(cut)) {
                seen[0]=true;var ballot=new TreeMap<>(object(active[0].promised().orElseThrow().value().get("ballot")));ballot.put("counter",9L);active[0].observeCurrent(ballot);
            }})) {
                active[0]=owner;if(cut.equals("before")) {var ballot=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));ballot.put("counter",9L);owner.observeCurrent(ballot);seen[0]=true;}
                retire(p,owner,0);retire(p,owner,0);assertTrue(seen[0]);V53StagedApplicationTest.noStaging(node);
                assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,()->helper.install(p,owner)).getMessage());
                assertArrayEquals(vote,Files.readAllBytes(node.resolve("pending.accept")));assertArrayEquals(journal,Files.readAllBytes(node.resolve("grants.gsr")));
            }
            assertEquals(0,resources.usage().leases());try(var owner=helper.open(p,resources,e->{})){retire(p,owner,0);helper.install(p,owner);assertTrue(owner.currentCertificate().isEmpty());}
            assertEquals(0,resources.usage().leases());
        }
    }
    @Test void retainedRetirementMarkerCannotChangeItsCoveringPlanOrLoseOriginalAuthority()throws Exception {
        var helper=helper();var p=prepared(helper,3,false);var f=p.f();Path node=f.request.targets().getFirst().replicaDirectory();var resources=new MembershipResources(512*MembershipResources.MIB);
        assertThrows(IOException.class,()->{try(var owner=helper.open(p,resources,e->{if(e.equals("SUPERSEDED_END_AUTHORITY_FORCED"))throw new IOException(e);})){retire(p,owner,0);}});
        var original=V53ReplayFilesTest.files(node);
        try(var owner=helper.open(p,resources,e->{})) {
            var ballot=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));ballot.put("counter",5L);
            assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(ballot));assertThrows(IllegalArgumentException.class,()->helper.install(p,owner));assertEquals(original,V53ReplayFilesTest.files(node));
        }
        Path marker=node.resolve("applied-end/retirement.gsat");var saved=Files.readAllBytes(marker);var body=new TreeMap<>(object(parse(Arrays.copyOfRange(saved,48,saved.length),16384)));
        var authority=new TreeMap<>(object(body.get("authority")));authority.put("coveringGeneration","0".repeat(64));body.put("authority",authority);byte[] encoded=canonical(body,16384);
        var buffer=java.nio.ByteBuffer.allocate(48+encoded.length);buffer.putInt(0x47534154).putShort((short)1).putShort((short)3).putInt(0).putInt(encoded.length);
        var digest=java.security.MessageDigest.getInstance("SHA-256");digest.update(Arrays.copyOf(buffer.array(),16));digest.update(encoded);buffer.put(digest.digest()).put(encoded);Files.write(marker,buffer.array());var changed=V53ReplayFilesTest.files(node);
        for(int attempt=0;attempt<2;attempt++) {
            var error=assertThrows(IllegalArgumentException.class,()->{try(var owner=helper.open(p,resources,e->{})){retire(p,owner,0);}});
            assertEquals("applied-end retirement authority/plan changed",error.getMessage());assertEquals(changed,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
        }
        Files.write(marker,saved);try(var owner=helper.open(p,resources,e->{})){retire(p,owner,0);helper.install(p,owner);}assertEquals(0,resources.usage().leases());
    }

}
