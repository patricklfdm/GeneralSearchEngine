package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual typed owners, TCP source and local durable bytes; historical quorum
 * fixtures remain conditional. No native joining vote or process death claim. */
class V53LearnerVoterStageTest {
    @TempDir Path temp;
    @BeforeEach void announce(TestInfo info){System.out.println("v53VoterStageCase="+info.getTestMethod().orElseThrow().getName());}
    V53LearnerCancellationTest.Fixture fixture(String phase,String change)throws Exception {
        var helper=new V53LearnerIntentTest();helper.temp=temp;return helper.fixture(phase,3,change,false);
    }
    static MembershipLearnerIntent intent(V53LearnerCancellationTest.Fixture f)throws IOException{return V53LearnerIntentTest.retain(f,e->{});}
    static Path stage(V53LearnerCancellationTest.Fixture f){return MembershipLearnerVoterStage.directory(f.local.summary);}
    @Test void stagesOwnFenceAtJointAndCompletedWithoutPublishingOrVoting()throws Exception {
        for(String phase:List.of("JOINT","COMPLETED"))try(var f=fixture(phase,"REPLACE");var intent=intent(f)) {
            var oldReplica=V53ReplayFilesTest.files(f.local.source.request.replicaDirectory());var oldTyped=V53ReplayFilesTest.files(f.local.typed());
            var usage=f.local.source.client.usage();var events=new ArrayList<String>();MembershipLearnerVoterStage.Ready ready;
            try(var staged=MembershipLearnerVoterStage.install(intent.forced(),events::add)) {
                ready=staged.readyCapability();ready.check();var source=intent.forced().source();var cert=source.membershipCertificateFence().orElseThrow();
                assertEquals(cert.value().get("ballot"),ready.promise().value().get("ballot"));assertNull(ready.promise().value().get("basisId"));
                assertEquals("node-6",ready.allocator().value().get("node"));
                assertEquals(object(cert.value().get("ballot")).get("counter"),ready.allocator().value().get("counter"));
                assertArrayEquals(ready.promise().bytes(),Files.readAllBytes(stage(f).resolve("grants.gsr")));
                assertFalse(Arrays.equals(intent.forced().member("promise.gsr"),ready.promise().bytes()));
                var manifest=decode(Files.readAllBytes(stage(f).resolve("generations/a/generation.gsr")),"records","GENERATION");
                assertEquals("node-6",manifest.value().get("node"));assertNull(manifest.value().get("basis"));assertNull(manifest.value().get("selection"));
                assertEquals(2,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
                assertTrue(events.indexOf("VOTER_STAGE_PAYLOAD_FORCED")<events.indexOf("VOTER_STAGE_READY_FORCED"));
                assertTrue(events.indexOf("VOTER_STAGE_READY_PARENT_FORCED")<events.indexOf("VOTER_STAGE_BEFORE_RETURN"));
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerVoterStage.resume(intent.forced(),e->fail("duplicate owner must not force")));
                assertThrows(Exception.class,()->MembershipBallotAllocator.openWithCurrentGeneration(stage(f),f.head.request().root(),f.head.request().identity(),e->fail("staging is not a voter")));
            }
            assertThrows(IllegalArgumentException.class,ready::check);assertEquals(usage,f.local.source.client.usage());
            assertEquals(oldReplica,V53ReplayFilesTest.files(f.local.source.request.replicaDirectory()));assertEquals(oldTyped,V53ReplayFilesTest.files(f.local.typed()));
            assertFalse(Files.exists(f.local.config.materialization().directory()));
        }
    }
    @Test void completeStageReopensFromOriginalIntentAndOwnerCloseRevokesReady()throws Exception {
        try(var f=fixture("JOINT","ADD")) {
            try(var intent=intent(f);var staged=MembershipLearnerVoterStage.install(intent.forced(),e->{})){staged.readyCapability().check();}
            var before=V53ReplayFilesTest.files(stage(f));f.reopen();
            try(var intent=MembershipLearnerIntent.resume(f.head,e->{})) {
                var usage=f.local.source.client.usage();var staged=MembershipLearnerVoterStage.resume(intent.forced(),e->{});var ready=staged.readyCapability();
                assertEquals(before,V53ReplayFilesTest.files(stage(f)));ready.check();intent.close();
                assertThrows(IllegalArgumentException.class,ready::check);assertTrue(staged.closed());
                assertTrue(f.local.source.client.usage().leases()<usage.leases());
            }
        }
    }
    @Test void interruptedMembersAndSealResumeOnlyTheExactOriginalPlan()throws Exception {
        for(String point:List.of("VOTER_STAGE_PLAN_WRITTEN","VOTER_STAGE_MEMBER_PREFIX_WRITTEN","VOTER_STAGE_IMAGE_WRITTEN",
                "VOTER_STAGE_PAYLOAD_FORCED","VOTER_STAGE_READY_PREFIX_WRITTEN","VOTER_STAGE_BEFORE_RETURN"))
            try(var f=fixture("JOINT","ADD");var intent=intent(f)) {
                var hit=new AtomicBoolean();var usage=f.local.source.client.usage();
                assertThrows(IOException.class,()->MembershipLearnerVoterStage.install(intent.forced(),event->{
                    if(point.equals(event)&&hit.compareAndSet(false,true))throw new IOException(point);
                }));assertTrue(hit.get());assertEquals(usage,f.local.source.client.usage());
                if(point.equals("VOTER_STAGE_MEMBER_PREFIX_WRITTEN")) {
                    Path member=stage(f).resolve("allocator.gsr");byte[] prefix=Files.readAllBytes(member),broken=prefix.clone();broken[0]^=1;Files.write(member,broken);
                    var before=V53ReplayFilesTest.files(stage(f));
                    assertThrows(Exception.class,()->MembershipLearnerVoterStage.resume(intent.forced(),e->fail("wrong prefix must not force")));
                    assertEquals(before,V53ReplayFilesTest.files(stage(f)));assertEquals(usage,f.local.source.client.usage());Files.write(member,prefix);
                }
                try(var restored=MembershipLearnerVoterStage.resume(intent.forced(),e->{})){restored.readyCapability().check();}
                assertEquals(usage,f.local.source.client.usage());
            }
    }
    @Test void missingOrTornPlanIsPreservedWithoutRecoveryWrites()throws Exception {
        for(String point:List.of("VOTER_STAGE_DIRECTORY_FORCED","VOTER_STAGE_PLAN_PREFIX_WRITTEN"))
            try(var f=fixture("JOINT","ADD");var intent=intent(f)) {
                assertThrows(IOException.class,()->MembershipLearnerVoterStage.install(intent.forced(),event->{if(event.equals(point))throw new IOException(point);}));
                var before=V53ReplayFilesTest.files(stage(f));var usage=f.local.source.client.usage();
                assertThrows(Exception.class,()->MembershipLearnerVoterStage.resume(intent.forced(),e->fail("incomplete decision must not force")));
                assertEquals(before,V53ReplayFilesTest.files(stage(f)));assertEquals(usage,f.local.source.client.usage());
            }
    }
    @Test void corruptedOrReplacedMembersCannotBeResealed()throws Exception {
        try(var f=fixture("JOINT","ADD");var intent=intent(f)) {
            try(var staged=MembershipLearnerVoterStage.install(intent.forced(),e->{})){staged.readyCapability().check();}
            var usage=f.local.source.client.usage();Path directory=stage(f);
            for(String name:List.of(MembershipLearnerVoterStage.PLAN,"grants.gsr","allocator.gsr","generations/a/source.gscp",MembershipLearnerVoterStage.READY)) {
                Path file=directory.resolve(name);byte[] good=Files.readAllBytes(file),bad=good.clone();bad[bad.length/2]^=1;Files.write(file,bad);
                var before=V53ReplayFilesTest.files(directory);
                assertThrows(Exception.class,()->MembershipLearnerVoterStage.resume(intent.forced(),e->fail("corruption must not force")));
                assertEquals(before,V53ReplayFilesTest.files(directory));assertEquals(usage,f.local.source.client.usage());Files.write(file,good);
            }
            Path original=directory.resolve("grants.gsr"),saved=f.local.base.resolve("saved-grants");Files.move(original,saved);Files.copy(saved,original);
            assertThrows(Exception.class,()->MembershipLearnerVoterStage.resume(intent.forced(),e->fail("copied inode must not force")));
            Files.delete(original);Files.move(saved,original);
            Path foreign=directory.resolve("foreign");Files.writeString(foreign,"foreign");
            assertThrows(Exception.class,()->MembershipLearnerVoterStage.resume(intent.forced(),e->fail("foreign member must not force")));Files.delete(foreign);
            try(var staged=MembershipLearnerVoterStage.resume(intent.forced(),e->{})) {
                var ready=staged.readyCapability();Files.writeString(foreign,"changed");assertThrows(Exception.class,ready::check);Files.delete(foreign);
                assertThrows(IllegalArgumentException.class,ready::check); // a failed owner never repairs itself
            }
        }
    }
    @Test void capacityAndRevokedIntentFailBeforeCreatingStage()throws Exception {
        try(var f=fixture("JOINT","ADD");var intent=intent(f)) {
            var forced=intent.forced();var resources=f.local.source.client;var usage=resources.usage();
            try(var busy=resources.reserve(MembershipResources.Unit.GENERATION,"occupied",1)) {
                assertThrows(IllegalArgumentException.class,()->MembershipLearnerVoterStage.install(forced,e->fail("capacity before writes")));
                assertFalse(Files.exists(stage(f)));
            }
            assertEquals(usage,resources.usage());intent.close();
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerVoterStage.install(forced,e->fail("closed intent must not write")));
            assertFalse(Files.exists(stage(f)));
        }
    }
    @Test void losingIntentDuringWriteRevokesStageAndPreservesPartialBytes()throws Exception {
        try(var f=fixture("JOINT","ADD");var intent=intent(f)) {
            var hit=new AtomicBoolean();
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerVoterStage.install(intent.forced(),event->{
                if(event.equals("VOTER_STAGE_MEMBER_FORCED") && hit.compareAndSet(false,true))intent.close();
            }));assertTrue(hit.get());assertFalse(Files.exists(stage(f).resolve(MembershipLearnerVoterStage.READY)));
            assertEquals(1,f.local.source.client.usage().counts().get(MembershipResources.Unit.GENERATION));
            assertTrue(Files.exists(stage(f).resolve("allocator.gsr")));
            try(var reopened=MembershipLearnerIntent.resume(f.head,e->{});var staged=MembershipLearnerVoterStage.resume(reopened.forced(),e->{})) {
                staged.readyCapability().check();
            }
        }
    }
}
