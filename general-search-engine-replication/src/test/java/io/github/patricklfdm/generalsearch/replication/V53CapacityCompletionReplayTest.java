package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class V53CapacityCompletionReplayTest {
    @TempDir Path temp;
    @Test void shortConditionalPrefixExercisesTheCompletePhysicalReplayPath()throws Exception {
        var application=new V53ApplicationReplayTest();application.temp=temp;
        var history=new V53EnvelopeHistoryFixture(application.initial(41),V53ApplicationImageTest.HISTORY,41);
        history.commit("BARRIER",null);
        var reservation=MembershipPublicationCapacity.publication(history.verify(),null,"RESERVE",8192,0);
        history.change(1,"SEAL");
        V53CapacityCompletionFixture.run(temp.resolve("owners"),Path.of("target/v53-capacity-completion/run-"+UUID.randomUUID()+"-smoke"),
                history,history.verify(),reservation,1,application);
    }
}
