package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class V53WorkPulseTest {
    @Test void noPulseBeforeActualReadinessAndOnlyAtDueInterval()throws Exception {
        var clock=new AtomicLong(100);var calls=new AtomicInteger();var pulse=new MembershipWorkPulse(clock::get,10);
        clock.set(1000);pulse.due(calls::incrementAndGet);assertEquals(0,calls.get());pulse.completed();
        clock.set(1009);pulse.due(calls::incrementAndGet);assertEquals(0,calls.get());
        clock.set(1010);pulse.due(calls::incrementAndGet);assertEquals(1,calls.get());
    }
    @Test void slowSampleDoesNotBurstAndExplicitHeartbeatRearmsSameInterval()throws Exception {
        var clock=new AtomicLong();var calls=new AtomicInteger();var pulse=new MembershipWorkPulse(clock::get,10);pulse.completed();
        clock.set(10);pulse.due(()->{calls.incrementAndGet();clock.set(100);});
        pulse.due(calls::incrementAndGet);assertEquals(1,calls.get());
        clock.set(109);pulse.completed();clock.set(110);pulse.due(calls::incrementAndGet);assertEquals(1,calls.get());
        clock.set(119);pulse.due(calls::incrementAndGet);assertEquals(2,calls.get());
    }
    @Test void nestedProgressCannotStartOverlappingSample()throws Exception {
        var clock=new AtomicLong();var pulse=new MembershipWorkPulse(clock::get,10);pulse.completed();clock.set(10);
        pulse.due(()->pulse.due(()->fail("overlapping heartbeat")));
    }
    @Test void parentFailureIsPropagatedWithoutAnyReplacementDeadline()throws Exception {
        var clock=new AtomicLong();var pulse=new MembershipWorkPulse(clock::get,10);pulse.completed();clock.set(20);
        var failure=new IOException("original lifetime expired");
        assertSame(failure,assertThrows(IOException.class,()->pulse.due(()->{throw failure;})));
        assertEquals(20,clock.get());
    }
    @Test void backwardsClockDoesNotAuthorizeAPulse()throws Exception {
        var clock=new AtomicLong(10);var pulse=new MembershipWorkPulse(clock::get,10);pulse.completed();clock.set(9);
        assertThrows(IllegalArgumentException.class,()->pulse.due(()->fail("backwards pulse")));
    }
}
