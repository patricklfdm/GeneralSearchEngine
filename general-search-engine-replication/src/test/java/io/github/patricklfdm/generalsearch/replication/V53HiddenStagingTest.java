package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** A real majority has compacted past the lagging owner's applied endpoint. */
class V53HiddenStagingTest {
    @TempDir Path temp;
    V53CoveredPhasedVoteTest helper()throws Exception {
        var h=new V53CoveredPhasedVoteTest();h.temp=Files.createDirectory(temp.resolve("helper-"+UUID.randomUUID()));return h;
    }
    V53CoveredPhasedVoteTest.Prepared prepared(V53CoveredPhasedVoteTest helper,int size,boolean backup)throws Exception {
        return helper.prepared(size,backup,"CERTIFICATE",f->{
            for(var target:f.request.targets().subList(0,size-(size/2+1))) {
            var vote=MembershipPendingAccept.decode(Files.readAllBytes(target.replicaDirectory().resolve("pending.accept")));
            var phased=f.observations.stream().filter(o->o.record().equals(vote.accept().digest()) || o.record().equals(vote.proof().digest())).collect(java.util.stream.Collectors.toSet());
            try(var owner=f.open(target,"lagging-apply")) {
                var result=owner.applyCurrent(builder().configuration(),target.materialization(),phased);
                f.observations.add(result.endorsement().owned());
                result.endorsement().parent().ifPresent(parent->f.observations.add(parent.owned()));
                result.endorsement().ancestors().forEach(parent->f.observations.add(parent.owned()));
            }
            }
            f.snapshot("lagging-applied");
            var barrier=V53DistinctMinorityTest.entry(f,new byte[0],"BARRIER");Files.write(f.raw.resolve("barrier.gsr"),barrier.bytes());
            V53DistinctMinorityTest.publish(f,2,barrier,new byte[0],f.request.targets().subList(size-(size/2+1),size));
        });
    }
    static List<MembershipSelection.Bridge> bridges(V53CoveredPhasedVoteTest.Prepared p) {
        return p.f().bridges.stream().filter(b->object(b.statement.value().get("start")).get("index").equals(1L)).toList();
    }
    static void retire(V53CoveredPhasedVoteTest.Prepared p,MembershipGrantJournal owner,int n,List<MembershipSelection.Bridge> bridges)throws Exception {
        owner.retireCoveredApplication(builder().configuration(),p.f().request.targets().get(n).materialization(),V53CoveredStagingTest.phased(p),
                p.installation().sources(),List.of(),List.of(),p.installation().images(),bridges);
    }
    @Test void laterPublishedRangeCanCoverAnOlderAppliedEndpointForAllProfiles()throws Exception {
        Path out=Path.of("target/v53-hidden-staging-profiles/run-"+UUID.randomUUID());Files.createDirectories(out);var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53HiddenStagingEvidence="+out.toAbsolutePath());
        try {
            for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
                var helper=helper();var p=prepared(helper,size,backup);var f=p.f();var targets=f.request.targets();int lagging=size-(size/2+1);
                try {
                    var longest=p.installation().sources().getLast().capsule;
                    assertEquals(2L,longest.terminal().cut().get("index"));assertNull(longest.anchor(1));assertEquals(1,bridges(p).size());
                    Files.write(f.raw.resolve("applied-ancestry.gsr"),MembershipGenerationPlan.ancestry(bridges(p)));
                    for(int i=0;i<lagging;i++)try(var owner=f.open(targets.get(i),"retire-hidden-application")) {retire(p,owner,i,bridges(p));retire(p,owner,i,bridges(p));}
                    f.snapshot("staging-retired");
                    for(var target:targets)try(var owner=f.open(target,"install-3")) {helper.install(p,owner);assertTrue(owner.currentCertificate().isEmpty());}
                    f.snapshot("round-3-installed");V53DistinctMinorityTest.maintain(f,"round-3-settled",targets,p.installation().obsolete());
                    var next=V53DistinctMinorityTest.campaign(f,4,targets);V53DistinctMinorityTest.maintain(f,"round-4-settled",targets,next.obsolete());
                    var barrier=V53DistinctMinorityTest.entry(f,new byte[0],"BARRIER");Files.write(f.raw.resolve("continued.gsr"),barrier.bytes());
                    V53DistinctMinorityTest.publish(f,3,barrier,new byte[0]);assertEquals(0,f.resources.usage().leases());
                }finally{V53CoveredPhasedVoteTest.save(f);}
                String name=size+"-"+(backup?"backup":"empty");V53JournalApplicationTest.copy(f.raw,out.resolve(name));
                rows.add(Map.of("case",name,"size",size,"backup",backup,"status","PASS"));System.out.println("v53HiddenStagingProfile="+name+" PASS");
            }
        }finally {Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-hidden-staging-v1","status",rows.size()==6?"PASS":"FAIL","cases",rows),65536));}
    }
    @Test void missingExtraUnownedAndAlteredProofsCannotDeleteStaging()throws Exception {
        var helper=helper();var p=prepared(helper,3,false);var t=p.f().request.targets().getFirst();var node=t.replicaDirectory();
        var proof=bridges(p).getFirst();var changed=new TreeMap<>(proof.statement.value());changed.put("catalogBefore","0".repeat(64));
        var changedStatement=decode(encode("records","CHECKPOINT",changed),"records","CHECKPOINT");
        var cases=List.of(List.<MembershipSelection.Bridge>of(),List.of(proof,proof),List.of(new MembershipSelection.Bridge(proof.statement,proof.acknowledgements,Set.of())),
                List.of(new MembershipSelection.Bridge(changedStatement,proof.acknowledgements,proof.owned)));
        for(var invalid:cases) {
            var before=V53ReplayFilesTest.files(node);
            try(var owner=p.f().open(t,"refuse-invalid-ancestry")){assertThrows(IllegalArgumentException.class,()->retire(p,owner,0,invalid));}
            assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,p.f().resources.usage().leases());
        }
        try(var owner=p.f().open(t,"refuse-plan-ancestry")) {
            assertEquals("unused/duplicate installation ancestry",assertThrows(IllegalArgumentException.class,()->owner.installCurrent(p.installation().sources(),List.of(),bridges(p),p.installation().images())).getMessage());
        }
        try(var owner=p.f().open(t,"complete")){retire(p,owner,0,bridges(p));helper.install(p,owner);}
    }
    @Test void repeatedRetirementInterruptionsRetainExactProofAndInstallation()throws Exception {
        var helper=helper();var p=prepared(helper,3,false);var f=p.f();Path node=f.request.targets().getFirst().replicaDirectory(),seed=temp.resolve("seed");V53JournalApplicationTest.copy(node,seed);
        var rows=new ArrayList<Map<String,Object>>();int n=0;
        Files.write(f.raw.resolve("applied-ancestry.gsr"),MembershipGenerationPlan.ancestry(bridges(p)));
        for(String cut:List.of("SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN","SUPERSEDED_END_AUTHORITY_FORCED","SUPERSEDED_END_FILE_DELETED","SUPERSEDED_END_RETIREMENT_DELETED")) {
            Files.move(node,temp.resolve("previous-"+n++));V53JournalApplicationTest.copy(seed,node);var resources=new MembershipResources(512*MembershipResources.MIB);
            Path raw=Files.createDirectory(f.raw.resolve("interrupted-"+cut));var first=new ArrayList<String>();
            assertThrows(IOException.class,()->{try(var owner=helper.open(p,resources,e->{first.add(e);if(e.equals(cut))throw new IOException(e);})){retire(p,owner,0,bridges(p));}});
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("first"));
            var second=new ArrayList<String>();assertThrows(IOException.class,()->{try(var owner=helper.open(p,resources,e->{second.add(e);if(e.equals("SUPERSEDED_END_AUTHORITY_FORCED"))throw new IOException(e);})){retire(p,owner,0,bridges(p));}});
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("second"));
            var end=new ArrayList<String>();try(var owner=helper.open(p,resources,end::add)){retire(p,owner,0,bridges(p));}
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("final"));
            try(var owner=helper.open(p,resources,e->{})){helper.install(p,owner);assertEquals(2L,owner.floorCopyCurrent().capsule.context.cut.get("index"));}
            assertEquals(0,resources.usage().leases());V53JournalApplicationTest.copy(node,raw.resolve("installed"));
            Files.write(raw.resolve("events.json"),canonical(Map.of("first",first,"second",second,"final",end),1024*1024));rows.add(Map.of("cut",cut,"status","PASS"));
        }
        Files.write(f.raw.resolve("interruptions.json"),canonical(rows,16384));V53CoveredPhasedVoteTest.save(f);
        System.out.println("v53HiddenStagingInterruptions="+f.raw.toAbsolutePath());
    }
    @Test void alteredProofDigestInForcedRetirementCannotResume()throws Exception {
        var helper=helper();var p=prepared(helper,3,false);var node=p.f().request.targets().getFirst().replicaDirectory();var resources=new MembershipResources(512*MembershipResources.MIB);
        assertThrows(IOException.class,()->{try(var owner=helper.open(p,resources,event->{if(event.equals("SUPERSEDED_END_AUTHORITY_FORCED"))throw new IOException(event);})){retire(p,owner,0,bridges(p));}});
        Path marker=node.resolve("applied-end/retirement.gsat");var original=Files.readAllBytes(marker);var body=new TreeMap<>(object(parse(Arrays.copyOfRange(original,48,original.length),16384)));
        var authority=new TreeMap<>(object(body.get("authority")));assertEquals(hash(MembershipGenerationPlan.ancestry(bridges(p))),authority.get("appliedAncestry"));
        authority.put("appliedAncestry","0".repeat(64));body.put("authority",authority);var payload=canonical(body,16384);
        var buffer=java.nio.ByteBuffer.allocate(48+payload.length);buffer.putInt(0x47534154).putShort((short)1).putShort((short)3).putInt(0).putInt(payload.length);
        var digest=java.security.MessageDigest.getInstance("SHA-256");digest.update(Arrays.copyOf(buffer.array(),16));digest.update(payload);buffer.put(digest.digest()).put(payload);Files.write(marker,buffer.array());
        var before=V53ReplayFilesTest.files(node);
        for(int i=0;i<2;i++) {
            var error=assertThrows(IllegalArgumentException.class,()->{try(var owner=helper.open(p,resources,e->{})){retire(p,owner,0,bridges(p));}});
            assertEquals("applied-end retirement authority/plan changed",error.getMessage());assertEquals(before,V53ReplayFilesTest.files(node));assertEquals(0,resources.usage().leases());
        }
        Files.write(marker,original);try(var owner=helper.open(p,resources,e->{})){retire(p,owner,0,bridges(p));helper.install(p,owner);}assertEquals(0,resources.usage().leases());
    }
}
