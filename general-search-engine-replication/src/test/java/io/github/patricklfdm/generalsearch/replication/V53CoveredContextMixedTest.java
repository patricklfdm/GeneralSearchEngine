package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Mixed original ballots with an actually admitted, later covered context. */
class V53CoveredContextMixedTest {
    @TempDir Path temp;
    record Mixed(V53CoveredContextTest.Prepared prepared,Map<String,String> oldest,boolean headroom) {}
    @FunctionalInterface interface BeforeReclaim { void run(V53BootstrapPublicationTest.Fixture f,Map<String,String> ids)throws Exception; }
    Mixed prepared(int size,boolean backup)throws Exception {return prepared(size,backup,null);}
    Mixed prepared(int size,boolean backup,BeforeReclaim check)throws Exception {
        var driver=new V53CoveredContextTest();driver.temp=Files.createDirectory(temp.resolve("driver-"+UUID.randomUUID()));
        var original=driver.original(size,backup,"CERTIFICATE");var f=original.f();var all=f.request.targets();
        var majority=all.subList(size-(size/2+1),size);var minority=all.subList(0,size-(size/2+1));
        try {
            for(var t:majority)try(var owner=f.open(t,"mixed-reaccept")){f.observations.add(owner.acceptRetainedCurrent(original.entry(),original.payload()));}
            f.snapshot("mixed-reaccepted");
            var mixed=V53DistinctMinorityTest.campaign(f,4,all);
            for(var t:all)try(var owner=f.open(t,"mixed-context")) {
                var vote=MembershipPendingAccept.decode(Files.readAllBytes(t.replicaDirectory().resolve("pending.accept")));
                assertEquals(minority.contains(t)?2L:3L,object(vote.accept().value().get("ballot")).get("counter"));
                assertEquals(mixed.sources().getLast().accepted.digest(),owner.currentOwnedTail().orElseThrow().record());
                owner.retainPendingContext();
            }
            f.snapshot("mixed-contexts");
            var copies=new ArrayList<MembershipFloor.Copy>();
            for(var t:majority)try(var owner=f.open(t,"mixed-floor-copy")){copies.add(owner.contextFloorCopy());}
            for(var t:majority)try(var owner=f.open(t,"mixed-floor")){owner.establishContextFloor(copies);}
            f.snapshot("mixed-floors");
            for(var t:all)try(var owner=f.open(t,"mixed-retirement")){owner.retireContextOriginal();}
            f.snapshot("mixed-retired");
            for(var t:majority)try(var owner=f.open(t,"mixed-source-retirement")){owner.retireSource(mixed.obsolete().get(t.identity().nodeId().value()));}
            f.snapshot("mixed-sources-retired");
            boolean headroom=size>3;
            if(headroom) {
                var next=new TreeMap<>(f.ballot);next.put("counter",5L);var refusals=new ArrayList<Map<String,Object>>();
                for(var t:minority)for(int attempt=1;attempt<=2;attempt++) {
                    var before=V53ReplayFilesTest.files(t.replicaDirectory());
                    try(var owner=f.open(t,"headroom-refusal")) {
                        assertEquals(7,f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
                        var failure=assertThrows(MembershipOperationException.class,()->owner.prepareCurrent(next));
                        assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,failure.reason());
                        assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,failure.outcome());
                        assertEquals("original source retention capacity",failure.getMessage());
                        assertEquals("higher ballot observed; fresh campaign required",assertThrows(IllegalArgumentException.class,()->owner.acceptRetainedCurrent(original.entry(),original.payload())).getMessage());
                        refusals.add(Map.of("node",t.identity().nodeId().value(),"attempt",attempt,"reason",failure.reason().name(),"outcome",failure.outcome().name(),"status","PASS"));
                    }
                    assertEquals(before,V53ReplayFilesTest.files(t.replicaDirectory()));assertEquals(0,f.resources.usage().leases());
                }
                f.snapshot("headroom-refused");Files.write(f.raw.resolve("headroom-refusals.json"),canonical(refusals,16384));
                var floorCopies=new ArrayList<MembershipFloor.Copy>();
                for(var t:all)try(var owner=f.open(t,"headroom-floor-copy")){floorCopies.add(owner.contextFloorCopy());}
                for(var t:minority)try(var owner=f.open(t,"headroom-reaccept")){f.observations.add(owner.acceptRetainedCurrent(original.entry(),original.payload()));}
                f.snapshot("headroom-reaccepted");
                for(var t:minority)try(var owner=f.open(t,"headroom-floor")) {
                    var quorum=new ArrayList<MembershipFloor.Copy>();quorum.add(floorCopies.stream().filter(c->c.owner.equals(t.identity())).findFirst().orElseThrow());
                    floorCopies.stream().filter(c->!c.owner.equals(t.identity())).limit(size/2).forEach(quorum::add);
                    owner.establishFloor(quorum);
                }
                f.snapshot("headroom-floors");if(check!=null)check.run(f,mixed.obsolete());
                for(var t:minority)try(var owner=f.open(t,"headroom-reclaim")){owner.retireSource(mixed.obsolete().get(t.identity().nodeId().value()));owner.releaseFloor();}
                f.snapshot("headroom-reclaimed");
            }
            for(var t:majority)try(var owner=f.open(t,"majority-reaccept")){f.observations.add(owner.acceptRetainedCurrent(original.entry(),original.payload()));}
            f.snapshot("majority-reaccepted");V53DistinctMinorityTest.publish(f,1,original.entry(),original.payload(),majority);
            var advanced=V53DistinctMinorityTest.campaign(f,5,all,false);f.snapshot("advanced-selected");
            return new Mixed(new V53CoveredContextTest.Prepared(f,advanced),mixed.obsolete(),headroom);
        }finally{V53CoveredPhasedVoteTest.save(f);}
    }
    static void complete(Mixed mixed)throws Exception {
        var p=mixed.prepared();var f=p.f();var all=f.request.targets();var minority=all.subList(0,all.size()-(all.size()/2+1));
        try {
            for(var t:all)try(var owner=f.open(t,"install-5")){V53CoveredContextTest.install(p,owner);assertTrue(owner.currentOwnedTail().isEmpty());assertTrue(owner.currentCertificate().isEmpty());}
            f.snapshot("covered-installed");
            if(!mixed.headroom())for(var t:minority)try(var owner=f.open(t,"release-covered-floor")){owner.retireInactive();owner.releaseFloor();}
            f.snapshot("floor-released");var copies=new ArrayList<MembershipFloor.Copy>();
            for(var t:all)try(var owner=f.open(t,"round-5-settled-copy")){copies.add(owner.floorCopyCurrent());}
            for(var t:all)try(var owner=f.open(t,"round-5-settled-maintain")) {
                var quorum=new ArrayList<MembershipFloor.Copy>();quorum.add(copies.stream().filter(c->c.owner.equals(t.identity())).findFirst().orElseThrow());
                copies.stream().filter(c->!c.owner.equals(t.identity())).limit(all.size()/2).forEach(quorum::add);
                owner.establishFloor(quorum);owner.retireInactive();String node=t.identity().nodeId().value();
                if(minority.contains(t) && !mixed.headroom())owner.retireSource(mixed.oldest().get(node));
                owner.retireSource(p.installation().obsolete().get(node));owner.releaseFloor();owner.rotateJournal();
            }
            f.snapshot("round-5-settled");var next=V53DistinctMinorityTest.campaign(f,6,all);
            V53DistinctMinorityTest.maintain(f,"round-6-settled",all,next.obsolete());
            var barrier=V53DistinctMinorityTest.entry(f,new byte[0],"BARRIER");Files.write(f.raw.resolve("barrier.gsr"),barrier.bytes());
            V53DistinctMinorityTest.publish(f,2,barrier,new byte[0]);assertEquals(0,f.resources.usage().leases());
        }finally{V53CoveredPhasedVoteTest.save(f);}
    }
    @Test void mixedOriginalBallotsRemainRecoverableAfterMajorityPublication()throws Exception {
        Path out=Path.of("target/v53-covered-context-mixed/run-"+UUID.randomUUID());Files.createDirectories(out);var rows=new ArrayList<Map<String,Object>>();
        System.out.println("v53CoveredContextMixedEvidence="+out.toAbsolutePath());
        try {
            for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
                var mixed=prepared(size,backup);var p=mixed.prepared();complete(mixed);String name=size+"-"+(backup?"backup":"empty");
                V53JournalApplicationTest.copy(p.f().raw,out.resolve(name));rows.add(Map.of("case",name,"status","PASS","size",size,"backup",backup));
                System.out.println("v53CoveredContextMixedCase="+name+" PASS");System.out.flush();
            }
        }finally{Files.write(out.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-covered-context-mixed-v1","status",rows.size()==6?"PASS":"FAIL","cases",rows),65536));}
    }
}
