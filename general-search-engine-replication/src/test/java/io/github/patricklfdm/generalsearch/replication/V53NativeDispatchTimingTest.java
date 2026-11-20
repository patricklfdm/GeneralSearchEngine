package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.object;

class V53NativeDispatchTimingTest {
    @TempDir Path temp;
    private static final long LIMIT=TimeUnit.HOURS.toNanos(20);

    private V53NativeDispatchTest.Network network(V53JoiningIntentExportTest.RunTiming timing)throws Exception {
        var seed=new V53NativeSeedTest();seed.temp=temp;
        var fixture=new V53NativeDispatchTest();fixture.temp=temp;
        return fixture.new Network(seed.request(3,true),V53RoundDriverTest.controlBounds(300_000),
                V53NativeDispatchTest.BUDGET,f->{},true,false,V53WireArchive.Layout.SEGMENTED_BACKUP,
                V53NativeResourceProfile.DEFAULT_SNAPSHOT_STAGING,timing);
    }
    @Test void directWorkAtHourEightSharesTheSameEndAsTheJoiningHistory()throws Exception {
        long start=System.nanoTime()-TimeUnit.HOURS.toNanos(8);
        try(var n=network(new V53JoiningIntentExportTest.RunTiming(true,start))) {
            var first=n.operationWindow("ACCEPT");var second=n.operationWindow("PUBLISH");
            assertEquals(start+LIMIT,first.started()+first.budget());
            assertEquals(start+LIMIT,second.started()+second.budget());
            assertTrue(second.budget()<=first.budget());
            assertTrue(second.budget()>TimeUnit.MILLISECONDS.toNanos(n.bounds.requestTimeoutMillis()));
        }
    }
    @Test void expiredDirectSendAndVoteObservationStopBeforeRemoteWork()throws Exception {
        try(var n=network(new V53JoiningIntentExportTest.RunTiming(true,System.nanoTime()-LIMIT))) {
            var basis=n.owners.getFirst().beginActivation().basis;
            n.ballot=object(basis.value().get("ballot"));
            var request=n.request(1,"ACCEPT",Map.of("acceptance","0".repeat(64)));
            n.beforeSend.set(frame->{throw new AssertionError("expired operation sent a request");});
            var send=assertThrows(AssertionError.class,()->n.send(1,request));
            assertTrue(send.getMessage().contains("maximum native round deadline"));
            var observe=assertThrows(AssertionError.class,()->n.observation(1,basis));
            assertTrue(observe.getMessage().contains("maximum native round deadline"));
        }
    }
    @Test void ordinaryFixtureStillUsesThreeMinutesForEachDirectOperation()throws Exception {
        var fixture=new V53NativeDispatchTest();fixture.temp=temp;
        try(var n=fixture.new Network()) {
            assertEquals(TimeUnit.SECONDS.toNanos(180),n.operationWindow("ACCEPT").budget());
        }
    }
}
