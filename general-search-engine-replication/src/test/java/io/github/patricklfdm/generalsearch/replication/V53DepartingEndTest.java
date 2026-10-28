package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual nonvoting end files under conditional original authority. This is not a native FINAL publication. */
class V53DepartingEndTest {
    @TempDir Path temp;
    static final long LIMIT=MembershipResources.Unit.JOURNAL.bytes;
    static final Set<String> FILES=Set.of("plan.json","selector.gsr","certificate.gsr","catalog.gsr","statement.gsr","application.image");
    static final List<String> PROFILES=List.of("4-REMOVE","5-REMOVE","3-REPLACE","4-REPLACE","5-REPLACE");
    static MembershipCheckpointPlan plan(String profile) {
        var p=profile.split("-");var fixture=new V53CapsuleFixture(Integer.parseInt(p[0]),p[1],6);
        return V53CheckpointPlanTest.plan(fixture.verify(),fixture.source,6);
    }
    static MembershipIdentity local(String profile){return V53DeclarationsTest.node(Integer.parseInt(profile.substring(0,1)));}
    static Decoded selector(MembershipCheckpointPlan plan,MembershipIdentity local) {
        return decode(encode("records","SELECTOR",Map.of("root",plan.catalog.value().get("root"),"node",local.nodeId().value(),"generation","a","digest",V53ContextFixture.H)),"records","SELECTOR");
    }
    static List<String> cuts() {
        var result=new ArrayList<>(List.of("APPLY_VALIDATED","APPLY_DIRECTORY_CREATED"));
        for(String prefix:List.of("APPLY_PLAN","APPLY_METADATA","APPLY_IMAGE"))
            for(String suffix:List.of("CREATED","PREFIX_WRITTEN","WRITTEN","FORCED"))result.add(prefix+"_"+suffix);
        result.addAll(List.of("APPLY_END_FORCED","APPLY_NONVOTING_DIRECTORY_FORCED","APPLY_BEFORE_RETURN"));return List.copyOf(result);
    }
    static MembershipResources resources(){return new MembershipResources(512*MembershipResources.MIB);}
    static MembershipResources.Lease journal(MembershipResources r){return r.reserve(MembershipResources.Unit.JOURNAL,"conditional-end-owner",LIMIT);}
    static Map<String,String> files(Path root)throws IOException {
        var result=new TreeMap<String,String>();if(Files.exists(root))try(var stream=Files.list(root)) {
            for(var p:stream.toList())result.put(p.getFileName().toString(),hash(Files.readAllBytes(p)));
        }return result;
    }
    @Test void allFiveDeparturesForceCompleteEndWithoutAnySuccessorObservation()throws Exception {
        for(String profile:PROFILES) {
            var plan=plan(profile);var local=local(profile);var selector=selector(plan,local);var r=resources();Path path=temp.resolve(profile);
            try(var lease=journal(r)) {
                try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                    // The legacy method must still reject before it writes or reserves an image.
                    assertThrows(IllegalArgumentException.class,()->store.force(plan,selector,local,()->{},e->{}));assertFalse(Files.exists(path));
                    var events=new ArrayList<String>();var result=store.forceCompletion(plan,selector,local,()->{},events::add);
                    assertInstanceOf(MembershipAppliedEndFiles.Departure.class,result);store.completed(plan,selector,local,result);
                    assertEquals(FILES,files(path).keySet());assertFalse(events.stream().anyMatch(e->e.startsWith("APPLY_ACK")));
                    assertTrue(events.indexOf("APPLY_END_FORCED")<events.indexOf("APPLY_NONVOTING_DIRECTORY_FORCED"));
                    assertEquals("APPLY_BEFORE_RETURN",events.getLast());assertEquals(1,r.usage().counts().get(MembershipResources.Unit.APPLICATION));
                    var forged=V53CheckpointPlanTest.endorsements(plan,List.of(local.nodeId().value()));
                    assertThrows(IllegalArgumentException.class,()->store.completed(plan,selector,local,
                        new MembershipAppliedEndFiles.Endorsement(forged.acks().getFirst(),forged.owned().iterator().next(),Optional.empty())));
                }
                var original=files(path);
                try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                    var recovered=store.forceCompletion(plan,selector,local,()->{},e->{});store.completed(plan,selector,local,recovered);
                    assertEquals(original,files(path));
                }
                assertEquals(Map.of(MembershipResources.Unit.JOURNAL,1),r.usage().counts());
            }assertEquals(0,r.usage().leases());
        }
    }
    @Test void survivingVotersStillRequireTheirExactForcedEndorsement()throws Exception {
        var plan=plan("5-REPLACE");var local=V53DeclarationsTest.node(1);var r=resources();Path path=temp.resolve("survivor");
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
            var result=store.forceCompletion(plan,selector(plan,local),local,()->{},e->{});
            var end=assertInstanceOf(MembershipAppliedEndFiles.Endorsement.class,result);
            assertEquals("node-1",end.owned().voter());assertTrue(Files.exists(path.resolve("ack.gsr")));
            store.completed(plan,selector(plan,local),local,result);
        }
    }
    @Test void noGeneralPermissionForLearnersKnownRemovedMembersOrForeignIncarnations()throws Exception {
        var f=new V53CapsuleFixture(3,"ADD",2);var preparing=V53CheckpointPlanTest.plan(f.verify(),f.source,2);
        var next=new V53CapsuleFixture(5,"REPLACE",7);var stable=V53CheckpointPlanTest.plan(next.verify(),next.source,7);
        var plan=plan("5-REPLACE");var wrong=new MembershipIdentity(local("5-REPLACE").nodeId(),new UUID(90,90),local("5-REPLACE").endpoint());
        var plans=List.of(preparing,stable,plan,plan);var identities=List.of(V53DeclarationsTest.node(4),V53DeclarationsTest.node(5),wrong,V53DeclarationsTest.node(9));
        for(int i=0;i<plans.size();i++) {
            var p=plans.get(i);var id=identities.get(i);var r=resources();Path path=temp.resolve("refused-"+i);
            try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                assertThrows(IllegalArgumentException.class,()->store.forceCompletion(p,selector(p,id),id,()->{},e->{}));assertFalse(Files.exists(path));
                assertEquals(Map.of(MembershipResources.Unit.JOURNAL,1),r.usage().counts());
            }
        }
    }
    @Test void allNonvotingCutsResumeTwiceAndRejectRevokedAuthority()throws Exception {
        var plan=plan("5-REPLACE");var local=local("5-REPLACE");var selector=selector(plan,local);
        for(String point:cuts()) {
            var r=resources();Path path=temp.resolve(point);
            try(var lease=journal(r)) {
                for(int attempt=0;attempt<2;attempt++)try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                    String cut=attempt==0?point:"APPLY_IMAGE_PREFIX_WRITTEN";boolean[] hit={false};
                    assertThrows(IOException.class,()->store.forceCompletion(plan,selector,local,()->{},e->{if(e.equals(cut)){hit[0]=true;throw new IOException("cut");}}));assertTrue(hit[0]);
                }
                try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {var result=store.forceCompletion(plan,selector,local,()->{},e->{});store.completed(plan,selector,local,result);}
                try(var store=new MembershipAppliedEndFiles(temp.resolve("fenced-"+point),r,LIMIT)) {
                    boolean[] fenced={false};MembershipGenerationFiles.Guard guard=()->{if(fenced[0])throw new IOException("fenced");};
                    assertThrows(IOException.class,()->store.forceCompletion(plan,selector,local,guard,e->{if(e.equals(point))fenced[0]=true;}));assertTrue(fenced[0]);
                }
            }assertEquals(0,r.usage().leases());
        }
    }
    @Test void completeFilesRejectChangedPlanFakeAckIncompleteImageAndInodeReplacement()throws Exception {
        var plan=plan("5-REPLACE");var local=local("5-REPLACE");var selector=selector(plan,local);var r=resources();Path path=temp.resolve("changed");
        try(var lease=journal(r)) {
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
                var result=store.forceCompletion(plan,selector,local,()->{},e->{});var original=files(path);
                var other=plan("4-REMOVE");var otherId=local("4-REMOVE");
                assertThrows(IllegalArgumentException.class,()->store.completed(other,selector(other,otherId),otherId,result));
                assertThrows(IllegalArgumentException.class,()->store.forceCompletion(other,selector(other,otherId),otherId,()->{},e->{}));assertEquals(original,files(path));
                Path image=path.resolve("application.image"),replacement=temp.resolve("image-copy");Files.copy(image,replacement);Files.move(replacement,image,StandardCopyOption.REPLACE_EXISTING);
                assertThrows(IllegalArgumentException.class,()->store.completed(plan,selector,local,result));
            }
            var fake=V53CheckpointPlanTest.endorsements(plan,List.of(local.nodeId().value()));Files.write(path.resolve("ack.gsr"),fake.acks().getFirst().bytes());
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {var original=files(path);assertThrows(IllegalArgumentException.class,()->store.forceCompletion(plan,selector,local,()->{},e->{}));assertEquals(original,files(path));}
            Files.delete(path.resolve("ack.gsr"));Files.write(path.resolve("application.image"),new byte[]{99});
            try(var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {var original=files(path);assertThrows(IllegalArgumentException.class,()->store.forceCompletion(plan,selector,local,()->{},e->{}));assertEquals(original,files(path));}
        }
    }
    @Test void capacityAndClosedOwnersNeverReturnCompletion()throws Exception {
        var plan=plan("4-REMOVE");var local=local("4-REMOVE");var r=resources();Path path=temp.resolve("small");
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,1)) {
            assertThrows(IllegalArgumentException.class,()->store.forceCompletion(plan,selector(plan,local),local,()->{},e->{}));assertFalse(Files.exists(path));
        }
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
            assertThrows(IllegalArgumentException.class,()->store.forceCompletion(plan,selector(plan,local),local,()->{},e->{if(e.equals("APPLY_END_FORCED"))store.close();}));
            assertFalse(Files.exists(path.resolve("ack.gsr")));
        }
        assertEquals(0,r.usage().leases());
    }
    @Test void nonvotingDerivedEndRetiresOnlyUnderExplicitCoveringAuthority()throws Exception {
        var plan=plan("5-REPLACE");var local=local("5-REPLACE");var r=resources();Path path=temp.resolve("retirement");
        try(var lease=journal(r);var store=new MembershipAppliedEndFiles(path,r,LIMIT)) {
            store.forceCompletion(plan,selector(plan,local),local,()->{},e->{});var original=files(path);
            assertThrows(IllegalArgumentException.class,()->store.retireSuperseded(plan,selector(plan,local),local,Map.of(),()->{},e->{}));assertEquals(original,files(path));
            store.retireSuperseded(plan,selector(plan,local),local,Map.of("conditionalCoveringGeneration",V53ContextFixture.H),()->{},e->{});
            assertFalse(Files.exists(path));assertEquals(Map.of(MembershipResources.Unit.JOURNAL,1),r.usage().counts());
        }
    }
}
