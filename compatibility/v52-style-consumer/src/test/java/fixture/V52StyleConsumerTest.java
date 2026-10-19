package fixture;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import io.github.patricklfdm.generalsearch.replication.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

class V52StyleConsumerTest {
    @TempDir Path root;
    @Test void stoppedHandleRejectsAllExplicitPoliciesWithoutIo() throws Exception {
        var config=V52StyleConsumer.request(root,null).replicas().getFirst();
        var token=new ReplicaReadToken(1,config.groupId(),new UUID(1,2),"00".repeat(32),0);
        V52StyleConsumer.CODEC_CALLS.set(0);
        try(var handle=V52StyleConsumer.stopped(config)) {
            for(var policy:ReplicaReadPolicy.values()) {
                var options=new ReplicaReadOptions(policy,policy==ReplicaReadPolicy.AT_LEAST_INDEX?Optional.of(token):Optional.empty(),0);
                var called=new AtomicBoolean();
                var future=handle.read(options,v->{called.set(true);return v.currentSequence();});
                assertTrue(future.isCompletedExceptionally());
                assertEquals(AutomaticReplicationException.Reason.NOT_READY,assertInstanceOf(AutomaticReplicationException.class,
                        assertThrows(CompletionException.class,future::join).getCause()).reason());
                assertFalse(called.get());
            }
        }
        assertEquals(0,V52StyleConsumer.CODEC_CALLS.get());
        try(var paths=Files.list(root)){assertEquals(0,paths.count());}
    }
    @Test void optionsAndImmutableTokenAreIndependentOfRuntime() {
        var token=new ReplicaReadToken(1,new ReplicationGroupId(new UUID(1,2)),new UUID(3,4),"ab".repeat(32),Long.MAX_VALUE);
        assertEquals(token,ReplicaReadToken.decode(token.encode()));
        assertThrows(IllegalArgumentException.class,()->new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.empty(),0));
        assertThrows(IllegalArgumentException.class,()->new ReplicaReadOptions(ReplicaReadPolicy.STALE_ALLOWED,Optional.empty(),1));
        assertDoesNotThrow(()->new ReplicaReadOptions(ReplicaReadPolicy.AT_LEAST_INDEX,Optional.of(token),60000));
    }
}
