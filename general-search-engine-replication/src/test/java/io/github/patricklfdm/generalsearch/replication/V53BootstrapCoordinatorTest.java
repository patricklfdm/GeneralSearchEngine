package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53BootstrapCoordinatorTest {
    @TempDir Path temp;
    MembershipBootstrapRequest<Integer,Doc> request(String name,int size,boolean backup)throws Exception {
        Path base=Files.createDirectory(temp.resolve(name));var helper=new V53BootstrapSeedTest();helper.temp=base;
        return helper.request(base,size,backup?helper.source("source",41):null);
    }
    static MembershipBootstrapPlanData original(Path operation,boolean candidate)throws IOException {
        return MembershipBootstrapPlanData.decode(Files.readAllBytes(operation.resolve(candidate?MembershipBootstrapPlanFiles.NEXT:MembershipBootstrapPlanFiles.FILE)),Files.readAllBytes(operation.resolve(MembershipBootstrapPlanFiles.IMAGE)));
    }
    @Test void randomHistoryAndBoundedProjectionSurviveExactPlanReopenAndPreparedRecovery()throws Exception {
        Path evidence=Path.of("target/v53-bootstrap-coordinator/run-"+UUID.randomUUID());Files.createDirectories(evidence);var rows=new ArrayList<Map<String,Object>>();var histories=new HashSet<UUID>();
        for(int size:List.of(3,4,5))for(boolean backup:List.of(false,true)) {
            var request=request("cohort-"+size+"-"+backup,size,backup);var checks=new AtomicInteger();
            MembershipBallotAllocator.Cut count=e->{if(e.equals("BOOTSTRAP_TYPED_RECHECKED"))checks.incrementAndGet();};
            var plan=MembershipBootstrapCoordinator.plan(builder().configuration(),request,count);var original=original(plan.operationDirectory(),false);
            assertEquals(4,original.seed.root.historyId().version());assertTrue(histories.add(original.seed.root.historyId()));assertEquals(1,checks.get());
            Path scratch=MembershipBootstrapCoordinator.projection(plan.operationDirectory());var before=V53BootstrapRecheckTest.projection(scratch);
            assertEquals(plan,MembershipBootstrapCoordinator.plan(builder().configuration(),request,count));assertEquals(2,checks.get());
            assertThrows(IOException.class,()->MembershipBootstrapCoordinator.apply(builder().configuration(),request,plan,false,e->{count.at(e);if(e.equals("BOOTSTRAP_PREPARED_DURABLE"))throw new IOException(e);}));
            assertEquals(3,checks.get());
            var result=MembershipBootstrapCoordinator.apply(builder().configuration(),request,plan,true,count);assertEquals(4,checks.get());
            assertEquals(original.seed.root,result.root());assertEquals(result,MembershipBootstrapCoordinator.readInitialResult(plan.operationDirectory()));
            assertEquals(before,V53BootstrapRecheckTest.projection(scratch));V53BootstrapTransactionTest.verify(original);
            Path member=Files.createDirectory(evidence.resolve("size-"+size+"-"+(backup?"backup":"empty")));
            Files.write(member.resolve("original-plan.gsbp"),original.bytes());Files.write(member.resolve("original-application.image"),original.seed.application());
            V53JournalApplicationTest.copy(scratch,member.resolve("planning-scratch"));if(backup)V53JournalApplicationTest.copy(request.sourcePath().orElseThrow(),member.resolve("original-source"));
            Files.write(member.resolve("receipt.gsbp"),Files.readAllBytes(plan.operationDirectory().resolve(MembershipBootstrapCommitData.RECEIPT)));
            V53BootstrapTransactionTest.copy(original,member.resolve("final"));
            rows.add(Map.of("case",member.getFileName().toString(),"size",size,"source",request.source().name(),"checks",checks.get(),"plan",original.digest(),"projectionBytes",V53BootstrapRevalidationTest.bytes(scratch),"status","PASS"));
        }
        Files.write(evidence.resolve("receipt.json"),canonical(Map.of("schema","gse-v53-bootstrap-coordinator-v1","status","PASS","cases",rows,"publicBootstrap",false,"freshProcesses",false),65536));
        System.out.println("v53BootstrapCoordinatorEvidence="+evidence.toAbsolutePath());
    }
    @Test void completeOriginalPlanCanBeRecoveredButMissingAndTornPlansCannotBeReinvented()throws Exception {
        var points=List.of("BOOTSTRAP_OPERATION_CREATED","BOOTSTRAP_IMAGE_PREFIX_WRITTEN","BOOTSTRAP_PLAN_PREFIX_WRITTEN","BOOTSTRAP_PLAN_WRITTEN","BOOTSTRAP_PLAN_RENAMED","BOOTSTRAP_PLAN_BEFORE_RETURN");
        for(int i=0;i<points.size();i++) {
            var r=request("cut-"+i,3,true);String stop=points.get(i);
            assertThrows(IOException.class,()->MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{if(e.equals(stop))throw new IOException(e);}));
            Path op=r.operationDirectory(),scratch=MembershipBootstrapCoordinator.projection(op);var before=V53ReplayFilesTest.files(op);var projection=V53BootstrapRecheckTest.projection(scratch);
            if(i<3) {
                assertThrows(Exception.class,()->MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{}));
                assertEquals(before,V53ReplayFilesTest.files(op));
            }else {
                var retained=original(op,i==3);var summary=MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{});
                assertEquals(retained.summary(),summary);assertArrayEquals(retained.bytes(),Files.readAllBytes(op.resolve(MembershipBootstrapPlanFiles.FILE)));
                assertFalse(Files.exists(op.resolve(MembershipBootstrapPlanFiles.NEXT)));assertEquals(summary,MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{}));
            }
            assertEquals(projection,V53BootstrapRecheckTest.projection(scratch));
        }
    }
    @Test void typedFailureDoesNotPromoteAnOriginalCandidateOrWriteADecision()throws Exception {
        var r=request("changed-source",3,true);
        assertThrows(IOException.class,()->MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{if(e.equals("BOOTSTRAP_PLAN_WRITTEN"))throw new IOException(e);}));
        Files.writeString(r.sourcePath().orElseThrow().resolve("gse-backup-checkpoint"),"changed");var before=V53ReplayFilesTest.files(r.operationDirectory());
        assertThrows(RuntimeException.class,()->MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{}));
        assertEquals(before,V53ReplayFilesTest.files(r.operationDirectory()));assertFalse(Files.exists(r.operationDirectory().resolve(MembershipBootstrapPlanFiles.FILE)));
        var empty=request("changed-projection",3,false);var plan=MembershipBootstrapCoordinator.plan(builder().configuration(),empty,e->{});
        Files.delete(MembershipBootstrapCoordinator.projection(plan.operationDirectory()).resolve("application-0/gse-backup-checkpoint"));var authority=V53BootstrapRevalidationTest.authority(original(plan.operationDirectory(),false));
        assertThrows(RuntimeException.class,()->MembershipBootstrapCoordinator.apply(builder().configuration(),empty,plan,false,e->{}));
        assertEquals(authority,V53BootstrapRevalidationTest.authority(original(plan.operationDirectory(),false)));assertFalse(Files.exists(plan.operationDirectory().resolve(MembershipBootstrapCommitData.JOURNAL)));
    }
    @Test void committingRecoveryUsesRetainedDecisionWithoutSourceButStillRequiresExactRequest()throws Exception {
        var r=request("committing",3,true);var plan=MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{});
        assertThrows(IOException.class,()->MembershipBootstrapCoordinator.apply(builder().configuration(),r,plan,false,e->{if(e.equals("BOOTSTRAP_COMMITTING_DURABLE"))throw new IOException(e);}));
        Files.move(r.sourcePath().orElseThrow(),temp.resolve("source-retained"));Files.move(MembershipBootstrapCoordinator.projection(r.operationDirectory()),temp.resolve("projection-retained"));
        var wrong=new MembershipBootstrapRequest<>(r.groupId(),r.configurationId(),r.source(),r.sourcePath(),r.targets(),r.operationDirectory(),r.maxSourceBytes(),r.maxOperationBytes()+1);
        var before=V53BootstrapRevalidationTest.authority(original(r.operationDirectory(),false));
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapCoordinator.apply(builder().configuration(),wrong,plan,true,e->{}));
        var configuration=io.github.patricklfdm.generalsearch.engine.SearchEngine.builder(Doc.class,ID).index(io.github.patricklfdm.generalsearch.index.IndexDefinition.prefix(VALUE)).configuration();
        assertThrows(IllegalArgumentException.class,()->MembershipBootstrapCoordinator.apply(configuration,r,plan,true,e->{}));assertEquals(before,V53BootstrapRevalidationTest.authority(original(r.operationDirectory(),false)));
        var result=MembershipBootstrapCoordinator.apply(builder().configuration(),r,plan,true,e->{assertNotEquals("BOOTSTRAP_TYPED_RECHECKED",e);});
        assertEquals(result,MembershipBootstrapCoordinator.readInitialResult(r.operationDirectory()));
        assertEquals(result,MembershipBootstrapCoordinator.apply(builder().configuration(),r,plan,true,e->{assertNotEquals("BOOTSTRAP_TYPED_RECHECKED",e);}));
    }
    @Test void occupiedProjectionAndInsufficientBudgetAreNotCleanedOrOverwritten()throws Exception {
        var r=request("occupied",3,false);Path scratch=MembershipBootstrapCoordinator.projection(r.operationDirectory());Files.createDirectory(scratch);Files.writeString(scratch.resolve("keep"),"keep");
        assertThrows(RuntimeException.class,()->MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{}));assertEquals("keep",Files.readString(scratch.resolve("keep")));assertFalse(Files.exists(r.operationDirectory()));
        var base=request("capacity",3,false);var small=new MembershipBootstrapRequest<>(base.groupId(),base.configurationId(),base.source(),base.sourcePath(),base.targets(),base.operationDirectory(),base.maxSourceBytes(),1);
        assertThrows(RuntimeException.class,()->MembershipBootstrapCoordinator.plan(builder().configuration(),small,e->{}));assertFalse(Files.exists(small.operationDirectory()));assertFalse(Files.exists(MembershipBootstrapCoordinator.projection(small.operationDirectory())));
    }
    @Test void aCorruptActivePlanNeverFallsBackToAnIntactCandidate()throws Exception {
        var r=request("corrupt-active",3,false);MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{});Path active=r.operationDirectory().resolve(MembershipBootstrapPlanFiles.FILE);
        Files.copy(active,r.operationDirectory().resolve(MembershipBootstrapPlanFiles.NEXT));Files.writeString(active,"corrupt");var before=V53ReplayFilesTest.files(r.operationDirectory());
        assertThrows(RuntimeException.class,()->MembershipBootstrapCoordinator.plan(builder().configuration(),r,e->{}));assertEquals(before,V53ReplayFilesTest.files(r.operationDirectory()));
    }
}
