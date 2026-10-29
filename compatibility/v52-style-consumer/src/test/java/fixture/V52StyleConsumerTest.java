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
    @Test void publishedTokenWireFormatAndDefensiveCopies() {
        // Independent genesis vector from the frozen read-tokens-v1 fixture.
        byte[] golden=HexFormat.of().parseHex("475352540100000000112233445566778899aabbccddeeff"
                +"ffeeddccbbaa99887766554433221100"+"0123456789abcdef".repeat(4)
                +"000000000000000004977343492e88ff0afa74eb1094ed69db252ce8187c2fe7a15f0c74947ab730");
        assertEquals(112,golden.length);
        var token=ReplicaReadToken.decode(golden);
        assertEquals(0,token.index());
        assertEquals(UUID.fromString("00112233-4455-6677-8899-aabbccddeeff"),token.groupId().value());
        assertArrayEquals(golden,token.encode());
        byte[] original=golden.clone();golden[8]^=1;
        byte[] encoded=token.encode();encoded[72]^=1;
        assertArrayEquals(original,token.encode());
        assertThrows(ReplicaReadException.class,()->ReplicaReadToken.decode(golden));
        assertThrows(ReplicaReadException.class,()->ReplicaReadToken.decode(Arrays.copyOf(original,113)));
        var result=new ReplicaReadResult<>("captured",ReplicaReadPolicy.AT_LEAST_INDEX,token,7);
        assertEquals(token,result.progress());
        assertEquals(7,result.applicationSequence());
    }
}
