package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.Unit;

class V53PendingRetainedCheckpointTest {
    @TempDir Path temp;
    @Test void retainingOriginalHistoryKeepsActualCheckpointPullWorkingUntilOwnerClose()throws Exception {
        var helper=new V53LearnerCheckpointEndpointTest();helper.temp=temp;
        try(var f=helper.new Fixture();var endpoint=f.listen(MembershipTransport.Events.NONE);var contact=f.contact()) {
            var before=f.fixture.f.local.source.client.usage();var source=f.pending.retainSource();source.check();
            assertEquals(before.metadata(),f.fixture.f.local.source.client.usage().metadata());
            assertEquals(before.staging(),f.fixture.f.local.source.client.usage().staging());
            assertEquals(1,f.fixture.f.local.source.client.usage().counts().get(Unit.SOURCE));
            assertFalse(f.fixture.f.local.source.client.usage().counts().containsKey(Unit.LEARNER));
            var result=f.fetch(contact::exchange);
            assertEquals(f.local.nodeId().value(),result.owned().voter());assertEquals(f.expected().digest(),result.acknowledgement().digest());
            f.pending.close();assertTrue(endpoint.closed());assertThrows(IllegalArgumentException.class,source::check);
            assertEquals(f.baseline,f.fixture.f.local.source.client.usage());
        }
    }
}
