package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.BUDGET;

class V53ControlCloseObservationsTest {
    @TempDir Path temp;
    static MembershipResources budget(int limit){return new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,4096,limit);}
    static long begin(MembershipResources.Lease lease){return lease.observeCloseBegin((MembershipResources.Lease)null);}
    @Test void disabledRecorderDoesNotChangeReservationOrClose() {
        var b=new MembershipResources(512*MIB);var lease=b.reserve(Unit.CONTROL,"test",10);
        assertEquals(-1,begin(lease));lease.close();lease.observeCloseReturned(-1);
        assertEquals(0,b.usage().leases());assertThrows(IllegalArgumentException.class,b::controlCloseObservations);
        assertThrows(IllegalArgumentException.class,()->new MembershipResources(METADATA_LIMIT,512*MIB,QUEUE_LIMIT,0,1));
    }
    @Test void nestedCallsKeepBothOrdersAndOriginalChildNames() {
        var b=budget(16);var parent=b.reserve(Unit.CONTROL,"parent",10);var child=b.reserve(Unit.CONTROL,"child",20);
        long p=parent.observeCloseBegin(child);long c=begin(child);child.close();child.observeCloseReturned(c);parent.close();parent.observeCloseReturned(p);
        var value=b.controlCloseObservations();assertFalse(value.failed());assertFalse(value.truncated());
        assertEquals(List.of("BEGIN","BEGIN","RETURNED","RETURNED"),value.rows().stream().map(MembershipControlCloseObservations.Row::event).toList());
        assertEquals(List.of(0L,1L,1L,0L),value.rows().stream().map(MembershipControlCloseObservations.Row::call).toList());
        assertEquals(List.of(2L,2L,3L,4L),value.rows().stream().map(MembershipControlCloseObservations.Row::resourceSequence).toList());
        assertEquals(List.of("child"),value.rows().getFirst().children());assertEquals(0,b.usage().leases());
    }
    @Test void foreignOrReleasedChildrenInvalidateOnlyTheObservation() {
        for(boolean foreign:List.of(false,true)) {
            var b=budget(16);var other=budget(16);var parent=b.reserve(Unit.CONTROL,"parent",10);
            var child=(foreign?other:b).reserve(Unit.CONTROL,"child",20);if(!foreign)child.close();
            assertEquals(-1,parent.observeCloseBegin(child));assertTrue(b.controlCloseObservations().failed());
            parent.close();child.close();assertEquals(0,b.usage().leases());assertEquals(0,other.usage().leases());
        }
    }
    @Test void truncatedRecorderCannotImplyNormalCloseQualification() {
        var b=budget(1);var lease=b.reserve(Unit.CONTROL,"test",10);long call=begin(lease);lease.close();lease.observeCloseReturned(call);
        assertTrue(b.controlCloseObservations().truncated());assertEquals(1,b.controlCloseObservations().rows().size());assertEquals(0,b.usage().leases());
    }
    @Test void childReferencesHaveAnIndependentBound() {
        var recorder=new MembershipControlCloseObservations(MembershipControlCloseObservations.MAXIMUM);
        var children=Collections.nCopies(256,"child");
        for(int i=0;i<1024;i++)recorder.record("BEGIN",-1,1,"parent",children);
        assertFalse(recorder.snapshot().truncated());recorder.record("BEGIN",-1,1,"parent",List.of("child"));
        assertTrue(recorder.snapshot().truncated());assertEquals(1024,recorder.snapshot().rows().size());
    }
    @Test void damagedRecorderCannotInterruptActualCleanup()throws Exception {
        var b=budget(8);var lease=b.reserve(Unit.CONTROL,"test",10);
        var field=MembershipResources.class.getDeclaredField("controlCloses");field.setAccessible(true);var recorder=field.get(b);
        var rows=MembershipControlCloseObservations.class.getDeclaredField("rows");rows.setAccessible(true);rows.set(recorder,null);
        assertEquals(-1,begin(lease));lease.close();lease.observeCloseReturned(-1);
        var failed=MembershipControlCloseObservations.class.getDeclaredField("failed");failed.setAccessible(true);
        assertEquals(true,failed.get(recorder));assertEquals(0,b.usage().leases());
    }
    @Test void concurrentResourceOwnersKeepOneTotalObservationOrder()throws Exception {
        var b=budget(1024);
        try(var executor=Executors.newFixedThreadPool(4)) {
            var jobs=new ArrayList<Future<?>>();
            for(int i=0;i<4;i++){int id=i;jobs.add(executor.submit(()->{for(int n=0;n<20;n++){
                var lease=b.reserve(Unit.CONTROL,"test-"+id+"-"+n,10);long c=begin(lease);lease.close();lease.observeCloseReturned(c);
            }}));}
            for(var job:jobs)job.get(10,TimeUnit.SECONDS);
        }
        long previous=0;var rows=b.controlCloseObservations().rows();assertEquals(160,rows.size());
        for(int i=0;i<rows.size();i++){assertEquals(i,rows.get(i).sequence());assertTrue(rows.get(i).resourceSequence()>=previous);previous=rows.get(i).resourceSequence();}
        assertEquals(0,b.usage().leases());
    }
    private static MembershipTransferExport wrap(MembershipTransferExport original,Runnable close) {
        return new MembershipTransferExport() {
            public MembershipContext context(){return original.context();}
            public MembershipIdentity identity(){return original.identity();}
            public Map<String,Object> ballot(){return original.ballot();}
            public Map<String,MembershipSourceExport.Content> references()throws IOException{return original.references();}
            public byte[] read(String digest,long offset,int maximum)throws IOException{return original.read(digest,offset,maximum);}
            public void close(){original.close();close.run();}
        };
    }
    @Test void throwingExporterDoesNotBecomeSuccessfulJustBecauseLeasesAreZero()throws Exception {
        var helper=new V53RecordExchangeTest();helper.temp=temp;
        try(var f=helper.new Local()) {
            var b=budget(16);var error=new IllegalStateException("export close failed");
            var export=wrap(f.export(f.owner.promised().orElseThrow()),()->{throw error;});
            var session=new MembershipSourceSession(export,f.fixture.request.targets().get(1).identity(),UUID.randomUUID(),b,1024,
                    MembershipFormat.FRAME,f.clock::get,0,BUDGET);
            assertSame(error,assertThrows(IllegalStateException.class,session::close));assertEquals(0,b.usage().leases());
            session.close();assertEquals(List.of("BEGIN"),b.controlCloseObservations().rows().stream().map(MembershipControlCloseObservations.Row::event).toList());
        }
    }
    @Test void slowExporterDoesNotHoldBudgetMonitorAndRepeatedSessionCloseDoesNoWork()throws Exception {
        var helper=new V53RecordExchangeTest();helper.temp=temp;
        try(var f=helper.new Local();var executor=Executors.newFixedThreadPool(2)) {
            var b=budget(16);var entered=new CountDownLatch(1);var released=new CountDownLatch(1);var calls=new AtomicInteger();
            var export=wrap(f.export(f.owner.promised().orElseThrow()),()->{
                calls.incrementAndGet();entered.countDown();try{assertTrue(released.await(10,TimeUnit.SECONDS));}catch(InterruptedException e){throw new AssertionError(e);}
            });
            var session=new MembershipSourceSession(export,f.fixture.request.targets().get(1).identity(),UUID.randomUUID(),b,1024,
                    MembershipFormat.FRAME,f.clock::get,0,BUDGET);
            var first=executor.submit(session::close);
            try {
                assertTrue(entered.await(10,TimeUnit.SECONDS));assertEquals(0,b.usage().leases());
                var other=executor.submit(()->{try(var lease=b.reserve(Unit.CONTROL,"unrelated",10)){return b.controlCloseObservations().rows().size();}});
                assertEquals(1,other.get(5,TimeUnit.SECONDS));
                var second=executor.submit(session::close);released.countDown();first.get(10,TimeUnit.SECONDS);second.get(10,TimeUnit.SECONDS);
            } finally {released.countDown();}
            session.close();assertEquals(1,calls.get());assertEquals(2,b.controlCloseObservations().rows().size());assertEquals(0,b.usage().leases());
        }
    }
}
