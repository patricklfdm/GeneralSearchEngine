package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53LearnerResourceOwnerTest {
    @TempDir Path temp;
    MembershipSourcePull pull(V53LearnerSourceTest.Fixture f,MembershipResources budget) {
        return MembershipSourcePull.learner(f.request,f.fixture.fixture.source.root,f.hint,budget,bounds(),f::deliver,()->{},f.clock::get,0,BUDGET);
    }
    @Test void successorRejectsForeignReceiverBeforePathsOrLeasesChangeAndAcceptsItsOwn()throws Exception {
        var helper=new V53LearnerMaterializationTest();helper.temp=temp;
        try(var f=helper.new Fixture();var typed=f.prepare(e->{})) {
            var prepared=typed.retainGeneration();var foreign=resources();var expected=f.source.client.usage();
            try(var prefix=pull(f.source,foreign);var generation=pull(f.source,foreign)) {
                prefix.fetchPrefix(f.base.resolve("foreign"));var copy=generation.fetchGeneration(prefix);var receiver=prefix.completeLearnerSource(copy,e->{});
                var before=foreign.usage();var originals=V53ReplayFilesTest.files(f.base.resolve("foreign"));
                assertEquals("learner retained foreign resource owner",assertThrows(IllegalArgumentException.class,
                        ()->MembershipLearnerSuccessor.install(prepared,receiver,copy,e->{})).getMessage());
                assertFalse(Files.exists(MembershipLearnerSuccessor.directory(f.summary)));assertEquals(expected,f.source.client.usage());
                assertEquals(before,foreign.usage());assertEquals(originals,V53ReplayFilesTest.files(f.base.resolve("foreign")));
            }
            assertEquals(0,foreign.usage().leases());
            try(var prefix=f.source.pull();var generation=f.source.pull()) {
                prefix.fetchPrefix(f.base.resolve("owned"));var copy=generation.fetchGeneration(prefix);
                var owner=MembershipLearnerSuccessor.install(prepared,prefix.completeLearnerSource(copy,e->{}),copy,e->{});
                assertArrayEquals(copy.capsule.packet.bytes(),owner.open(prepared).source().packet.bytes());
            }
        }
    }
    @Test void firstAdmissionAlsoRejectsAReceivingBudgetDifferentFromItsOperationOwner()throws Exception {
        var helper=new V53LearnerSourceTest();helper.temp=temp;
        try(var f=helper.new Fixture();var prefix=f.pull();var generation=f.pull()) {
            prefix.fetchPrefix(temp.resolve("source"));var copy=generation.fetchGeneration(prefix);var plan=MembershipLearnerAdmissionPlan.create(f.request,copy);
            var foreign=resources();
            try(var files=MembershipLearnerAdmissionFiles.create(plan,foreign,e->{},()->plan.checkOriginal(copy))){files.summary();}
            var receiver=prefix.completeLearnerSource(copy,e->{});var before=f.client.usage();
            assertEquals("learner retained foreign resource owner",assertThrows(IllegalArgumentException.class,()->MembershipLearnerStore.install(
                    MembershipLearnerAdmissionFiles.openAdmission(plan.summary(),foreign,e->{}),receiver,copy,e->{})).getMessage());
            assertEquals(before,f.client.usage());assertEquals(0,foreign.usage().leases());assertFalse(Files.exists(f.request.replicaDirectory()));
            assertFalse(Files.exists(f.request.operationDirectory().resolve(MembershipLearnerAdmissionFiles.RETAIN)));
        }
    }
}
