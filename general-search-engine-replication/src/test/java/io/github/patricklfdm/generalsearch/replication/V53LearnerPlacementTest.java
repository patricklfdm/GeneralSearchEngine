package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Actual typed learner, TCP INTENT and original moves. The historical quorum
 * is conditional; exception cuts and read-only inspection are not cold voting. */
class V53LearnerPlacementTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo test){System.out.println("v53LearnerPlacementCase="+test.getTestMethod().orElseThrow().getName());}
    V53LearnerCancellationTest.Fixture fixture()throws Exception {
        var helper=new V53LearnerIntentTest();helper.temp=temp;return helper.fixture("JOINT");
    }
    static Map<String,Object> keys(Path root)throws IOException {
        var result=new TreeMap<String,Object>();try(var walk=Files.walk(root)){for(Path path:walk.toList())result.put(root.relativize(path).toString(),MembershipBasisSources.key(path));}return result;
    }
    @Test void actualPlacementMovesOriginalPayloadsKeepsRootLocksAndLeavesNativeAdmissionClosed()throws Exception {
        try(var f=fixture();var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
            Path replica=f.local.source.request.replicaDirectory(),staged=MembershipLearnerVoterStage.directory(f.local.summary);
            var original=keys(staged);var preserved=new TreeMap<String,Object>();
            for(String name:List.of("root.gsr","node.gsr","replica.lock"))preserved.put(name,MembershipBasisSources.key(replica.resolve(name)));
            var usage=custody.usage();var events=new ArrayList<String>();
            try(var placed=MembershipLearnerPlacement.install(custody,events::add)) {
                placed.check();assertEquals(replica,placed.replica());assertEquals(usage,custody.usage());assertEquals(2,usage.counts().get(MembershipResources.Unit.GENERATION));
                for(var row:preserved.entrySet())assertEquals(row.getValue(),MembershipBasisSources.key(replica.resolve(row.getKey())));
                for(String name:MembershipLearnerPlacement.MOVES) {
                    assertFalse(Files.exists(staged.resolve(name)));assertEquals(original.get(name),MembershipBasisSources.key(replica.resolve(name)));
                    for(var row:original.entrySet())if(row.getKey().startsWith(name+"/"))assertEquals(row.getValue(),MembershipBasisSources.key(replica.resolve(row.getKey())));
                }
                assertTrue(events.indexOf("LEARNER_PLACEMENT_DECISION_FORCED")<events.indexOf("LEARNER_PLACEMENT_MOVED:genesis.gsr"));
                assertTrue(events.indexOf("LEARNER_PLACEMENT_PAYLOAD_FORCED")<events.indexOf("LEARNER_PLACEMENT_CREATED:"+MembershipLearnerPlacement.READY));
                new V53MembershipOwnershipTest().probe(replica.resolve("replica.lock"),f.local.source.request.operationDirectory().resolve("operation.lock"));
                assertThrows(Exception.class,f.head::check);f.local.store.close();f.typed.close();stage.close();intent.close();placed.check();assertEquals(usage,custody.usage());
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerPlacement.install(custody,e->fail("duplicate placement wrote")));
                assertEquals("PLACED",MembershipLearnerPlacement.inspectOriginal(f.local.summary).status());
            }
            assertEquals(0,f.local.source.client.usage().leases());var before=MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null);
            assertEquals(MembershipLearnerPlacement.MOVES.size(),MembershipLearnerPlacement.inspectOriginal(f.local.summary).moved());
            assertThrows(Exception.class,()->MembershipLearnerStore.resume(f.local.summary,f.local.source.client,e->fail("ordinary learner open must not write")));
            assertEquals(before,MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null));assertEquals(0,f.local.source.client.usage().leases());
        }
    }
    @Test void everyLiveMoveAndMarkerCutResumesSameInodesAndChargesUnderContinuousCustody()throws Exception {
        try(var f=fixture();var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
            var cuts=new ArrayDeque<String>();cuts.add("LEARNER_PLACEMENT_WRITTEN:"+MembershipLearnerPlacement.PLAN);
            for(String name:MembershipLearnerPlacement.MOVES)for(String phase:List.of("BEFORE_MOVE","MOVED","PARENTS_FORCED"))cuts.add("LEARNER_PLACEMENT_"+phase+":"+name);
            cuts.add("LEARNER_PLACEMENT_PREFIX_WRITTEN:"+MembershipLearnerPlacement.READY);cuts.add("LEARNER_PLACEMENT_WRITTEN:"+MembershipLearnerPlacement.READY);
            cuts.add("LEARNER_PLACEMENT_COMPLETE");var seen=new ArrayList<String>();var usage=custody.usage();
            MembershipBallotAllocator.Cut cut=event->{if(event.equals(cuts.peekFirst())){seen.add(cuts.removeFirst());throw new IOException(event);}};
            assertThrows(IOException.class,()->MembershipLearnerPlacement.install(custody,cut));
            Path plan=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerPlacement.PLAN);
            byte[] bytes=AdmissionPaths.read(plan,MembershipLearnerPlacement.MAXIMUM);Object key=MembershipBasisSources.key(plan);int expected=cuts.size()+1;
            while(!cuts.isEmpty()) {
                assertThrows(IOException.class,()->MembershipLearnerPlacement.resume(custody,cut));custody.check();assertEquals(usage,custody.usage());
                assertArrayEquals(bytes,AdmissionPaths.read(plan,MembershipLearnerPlacement.MAXIMUM));assertEquals(key,MembershipBasisSources.key(plan));
                MembershipLearnerPlacement.inspectOriginal(f.local.summary);
                new V53MembershipOwnershipTest().probe(f.local.source.request.replicaDirectory().resolve("replica.lock"));
            }
            assertEquals(expected,seen.size());MembershipLearnerPlacement.resume(custody,e->{}).check();assertEquals("PLACED",MembershipLearnerPlacement.inspectOriginal(f.local.summary).status());
            assertEquals(usage,custody.usage());
        }
    }
    @Test void tornDecisionOrLastBoundaryCorruptionCannotMovePayloadOrBecomeANewPlan()throws Exception {
        for(boolean corrupt:List.of(false,true))try(var f=fixture();var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
            var roots=MembershipLearnerCustody.roots(f.local.summary);var before=MembershipLearnerCustody.capture(roots,null);var hit=new AtomicBoolean();
            Path plan=MembershipLearnerPlacement.directory(f.local.summary).resolve(MembershipLearnerPlacement.PLAN);
            assertThrows(Exception.class,()->MembershipLearnerPlacement.install(custody,event->{
                if(!corrupt && event.equals("LEARNER_PLACEMENT_PREFIX_WRITTEN:"+MembershipLearnerPlacement.PLAN)){hit.set(true);throw new IOException(event);}
                if(corrupt && event.equals("LEARNER_PLACEMENT_BEFORE_MOVE:genesis.gsr")){hit.set(true);Files.writeString(plan,"changed");}
            }));assertTrue(hit.get());byte[] original=Files.readAllBytes(plan);
            assertThrows(Exception.class,()->MembershipLearnerPlacement.resume(custody,e->fail("invalid original must not write")));
            assertThrows(Exception.class,()->MembershipLearnerPlacement.inspectOriginal(f.local.summary));
            assertArrayEquals(original,Files.readAllBytes(plan));assertEquals(before,MembershipLearnerCustody.capture(roots,null));
            new V53MembershipOwnershipTest().probe(f.local.source.request.replicaDirectory().resolve("replica.lock"));
        }
    }
    @Test void readOnlyInspectionRejectsDuplicateMissingCopiedAndNonprefixLocationsWithoutRepair()throws Exception {
        try(var f=fixture();var intent=V53LearnerIntentTest.retain(f,e->{});var stage=MembershipLearnerVoterStage.install(intent.forced(),e->{});
                var custody=MembershipLearnerCustody.take(stage.readyCapability(),e->{})) {
            var hit=new AtomicBoolean();assertThrows(IOException.class,()->MembershipLearnerPlacement.install(custody,event->{if(event.equals("LEARNER_PLACEMENT_MOVED:genesis.gsr")){hit.set(true);throw new IOException(event);}}));
            assertTrue(hit.get());assertEquals(1,MembershipLearnerPlacement.inspectOriginal(f.local.summary).moved());
            Path replica=f.local.source.request.replicaDirectory(),staged=MembershipLearnerVoterStage.directory(f.local.summary);
            Path moved=replica.resolve("genesis.gsr"),saved=f.local.base.resolve("original-genesis");var originals=MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null);
            for(String fault:List.of("duplicate","missing","copied","nonprefix","foreign")) {
                switch(fault) {
                    case "duplicate" -> Files.copy(moved,staged.resolve("genesis.gsr"));
                    case "missing" -> Files.move(moved,saved);
                    case "copied" -> {Files.move(moved,saved);Files.copy(saved,moved);}
                    case "nonprefix" -> Files.move(staged.resolve(MembershipCurrentGeneration.SELECTOR),replica.resolve(MembershipCurrentGeneration.SELECTOR));
                    case "foreign" -> Files.writeString(replica.resolve("foreign"),"preserve");
                    default -> throw new AssertionError(fault);
                }
                var invalid=V53ReplayFilesTest.files(replica);assertThrows(Exception.class,()->MembershipLearnerPlacement.inspectOriginal(f.local.summary));assertEquals(invalid,V53ReplayFilesTest.files(replica));
                switch(fault) {
                    case "duplicate" -> Files.delete(staged.resolve("genesis.gsr"));
                    case "missing" -> Files.move(saved,moved);
                    case "copied" -> {Files.delete(moved);Files.move(saved,moved);}
                    case "nonprefix" -> Files.move(replica.resolve(MembershipCurrentGeneration.SELECTOR),staged.resolve(MembershipCurrentGeneration.SELECTOR));
                    case "foreign" -> Files.delete(replica.resolve("foreign"));
                    default -> throw new AssertionError(fault);
                }
                assertEquals(originals,MembershipLearnerCustody.capture(MembershipLearnerCustody.roots(f.local.summary),null));custody.check();
            }
            MembershipLearnerPlacement.resume(custody,e->{}).check();
        }
    }
}
