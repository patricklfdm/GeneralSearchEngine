package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.BUDGET;

class V53TransferCloseDrainTest {
    @TempDir Path temp;
    static void await(CountDownLatch gate)throws IOException {
        try {if(!gate.await(20,TimeUnit.SECONDS))throw new IOException("transfer drain test gate expired");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("transfer drain test interrupted",error);}
    }
    static void interruptedClose(MembershipTransferService service) {
        Thread.currentThread().interrupt();
        try {assertEquals("transfer service close interrupted",assertThrows(IllegalStateException.class,service::close).getMessage());}
        finally {assertTrue(Thread.interrupted());}
    }
    @ParameterizedTest @ValueSource(strings={"TRANSFER_ADMITTED","TRANSFER_BEFORE_REPLY"})
    void interruptedDrainKeepsAdmittedCallAndMetadataUntilRetry(String point)throws Exception {
        var helper=new V53TransferServiceTest();helper.temp=temp;
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var l=helper.new Local(2,(event,q,a)->{if(event.equals(point)){entered.countDown();await(release);}})) {
            var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());
            var call=CompletableFuture.runAsync(()->assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request)));
            try {
                assertTrue(entered.await(10,TimeUnit.SECONDS));interruptedClose(l.service);
                assertEquals(1,l.service.usage().calls());assertTrue(l.service.usage().closed());
                assertEquals(1,l.service.usage().traces());assertTrue(l.f.fixture.resources.usage().queued()>0);
                CompletableFuture.runAsync(()->assertThrows(IllegalArgumentException.class,
                        ()->l.service.handle(l.peer(2),request))).get(1,TimeUnit.SECONDS);
                interruptedClose(l.service);
            }finally {release.countDown();call.get(15,TimeUnit.SECONDS);l.service.close();}
            assertEquals(0,l.f.fixture.resources.usage().queued());
            assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request));
        }
    }
    @Test void concurrentCloseWaitsForOriginalExportRelease()throws Exception {
        var helper=new V53TransferServiceTest();helper.temp=temp;
        try(var l=helper.new Local();var executor=Executors.newFixedThreadPool(2)) {
            var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());
            assertEquals("SOURCE_OFFER",l.service.handle(l.peer(2),request).kind());
            Future<?> first,second;
            synchronized(l.f.owner) {
                first=executor.submit(l.service::close);
                V53MembershipTransportTest.waitFor(()->l.service.usage().closed());
                second=executor.submit(l.service::close);
                assertThrows(TimeoutException.class,()->second.get(200,TimeUnit.MILLISECONDS),
                        "another closer must not bypass a blocked original export release");
                assertTrue(l.f.fixture.resources.usage().queued()>0);
            }
            first.get(10,TimeUnit.SECONDS);second.get(10,TimeUnit.SECONDS);
            assertEquals(0,l.f.fixture.resources.usage().queued());
        }
    }
    @ParameterizedTest @ValueSource(strings={"TRANSFER_ADMITTED","TRANSFER_BEFORE_REPLY"})
    void handlerCannotReportItsOwnDrainComplete(String point)throws Exception {
        var helper=new V53TransferServiceTest();helper.temp=temp;
        var holder=new AtomicReference<MembershipTransferService>();var failure=new AtomicReference<Throwable>();
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        try(var l=helper.new Local(2,(event,q,a)->{if(event.equals(point)) {
            try{holder.get().close();}catch(Throwable error){failure.set(error);}
            entered.countDown();await(release);
        }})) {
            holder.set(l.service);var request=l.request(2,UUID.randomUUID(),l.f.source.basis.digest());
            var call=CompletableFuture.runAsync(()->assertThrows(IllegalArgumentException.class,()->l.service.handle(l.peer(2),request)));
            try {
                assertTrue(entered.await(10,TimeUnit.SECONDS));
                assertEquals("transfer close from active handler",assertInstanceOf(IllegalStateException.class,failure.get()).getMessage());
                interruptedClose(l.service);assertEquals(1,l.service.usage().calls());
            }finally{release.countDown();call.get(15,TimeUnit.SECONDS);l.service.close();}
        }
    }
    static MembershipTransferExport throwing(MembershipTransferExport original,RuntimeException failure,AtomicInteger calls) {
        return new MembershipTransferExport() {
            public List<MembershipResources.Lease> closeReservations(){return original.closeReservations();}
            public MembershipContext context(){return original.context();}
            public MembershipIdentity identity(){return original.identity();}
            public Map<String,Object> ballot(){return original.ballot();}
            public Map<String,MembershipSourceExport.Content> references()throws IOException{return original.references();}
            public byte[] read(String digest,long offset,int maximum)throws IOException{return original.read(digest,offset,maximum);}
            public void close(){calls.incrementAndGet();original.close();throw failure;}
        };
    }
    @Test void failedExporterCannotBecomeSuccessfulOnRepeatedSessionClose()throws Exception {
        var helper=new V53RecordExchangeTest();helper.temp=temp;
        try(var f=helper.new Local()) {
            var budget=V53ControlCloseObservationsTest.budget(16);var calls=new AtomicInteger();
            var failure=new IllegalStateException("original export close failure");
            var export=throwing(f.export(f.owner.promised().orElseThrow()),failure,calls);
            var session=new MembershipSourceSession(export,f.fixture.request.targets().get(1).identity(),UUID.randomUUID(),budget,
                    1024,FRAME,f.clock::get,0,BUDGET);
            assertSame(failure,assertThrows(IllegalStateException.class,session::close));
            assertSame(failure,assertThrows(IllegalStateException.class,session::close));assertEquals(1,calls.get());
            assertEquals(List.of("BEGIN"),budget.controlCloseObservations().rows().stream().map(MembershipControlCloseObservations.Row::event).toList());
        }
    }
    @Test void failingChildStillClosesOtherExportsAndKeepsItsParentFailed()throws Exception {
        var helper=new V53JoiningPreparationTest();helper.temp=temp;
        try(var l=helper.local();var publication=helper.publication(l)) {
            // This separate conditional budget isolates failed service metadata.
            // The original publication/exports remain owned by the real journal.
            var budget=V53ControlCloseObservationsTest.budget(32);var first=new AtomicReference<Decoded>();
            try(var pull=l.pull((p,q,k,d)->{
                first.set(q);return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.PROTOCOL,"capture initial original request",null));
            })) {
                assertThrows(MembershipTransport.Failure.class,()->pull.fetchPrefixMetadata(
                        MembershipJoiningPreparation.reference(l.reader.activationContext(),l.reader.activationIdentity()),MembershipJoiningPreparation.MAXIMUM));
            }
            var failure=new IllegalStateException("first export cleanup failed");var opened=new AtomicInteger();var failedCloses=new AtomicInteger();
            var service=MembershipTransferService.prefix(l.source,budget,V53SourceExchangeTest.bounds(),()->{},l.clock::get,0,BUDGET,
                    (p,q,k,d)->{throw new AssertionError("preparation reads need no outgoing quorum");},(reader,request)->{
                        var export=publication.open(reader,request);
                        return opened.getAndIncrement()==0?throwing(export,failure,failedCloses):export;
                    });
            var before=l.a.usage();var reader=l.reader.activationIdentity();
            assertEquals("SOURCE_OFFER",service.handle(reader,first.get()).kind());
            var other=new TreeMap<>(first.get().value());other.put("trace",UUID.randomUUID().toString());
            assertEquals("SOURCE_OFFER",service.handle(reader,decode(encode("wire","CHUNK",other),"wire","CHUNK")).kind());
            assertEquals(2,opened.get());assertTrue(l.a.usage().queued()>before.queued());
            assertSame(failure,assertThrows(IllegalStateException.class,service::close));
            assertEquals(before,l.a.usage(),"both original exports must close even if one reports failure");
            assertSame(failure,assertThrows(IllegalStateException.class,service::close));assertEquals(1,failedCloses.get());
            assertTrue(service.usage().closed());assertEquals(2,budget.usage().leases(),"failed trace and parent remain charged");
            var rows=budget.controlCloseObservations().rows();
            assertEquals(1,rows.stream().filter(r->r.owner().startsWith("transfer-service-") && r.event().equals("BEGIN")).count());
            assertEquals(0,rows.stream().filter(r->r.owner().startsWith("transfer-service-") && r.event().equals("RETURNED")).count());
            assertThrows(IllegalArgumentException.class,()->service.handle(reader,first.get()));
        }
    }
    @ParameterizedTest @ValueSource(booleans={false,true})
    void originalTransferFailureSurvivesFailingExportCleanup(boolean constructor)throws Exception {
        var helper=new V53JoiningPreparationTest();helper.temp=temp;
        try(var l=helper.local();var publication=helper.publication(l)) {
            var budget=V53ControlCloseObservationsTest.budget(32);var first=new AtomicReference<Decoded>();
            try(var pull=l.pull((p,q,k,d)->{first.set(q);return CompletableFuture.failedFuture(
                    new MembershipTransport.Failure(MembershipTransport.Reason.PROTOCOL,"capture request",null));})) {
                assertThrows(MembershipTransport.Failure.class,()->pull.fetchPrefixMetadata(
                        MembershipJoiningPreparation.reference(l.reader.activationContext(),l.reader.activationIdentity()),MembershipJoiningPreparation.MAXIMUM));
            }
            var primary=new IOException("original transfer failure");var cleanup=new IllegalStateException("export cleanup failure");var closes=new AtomicInteger();
            var service=MembershipTransferService.prefix(l.source,budget,V53SourceExchangeTest.bounds(),()->{},l.clock::get,0,BUDGET,
                    (p,q,k,d)->{throw new AssertionError("no outgoing quorum");},(reader,request)->{
                var original=publication.open(reader,request);var references=new AtomicInteger();
                return new MembershipTransferExport() {
                    public List<MembershipResources.Lease> closeReservations(){return original.closeReservations();}
                    public MembershipContext context(){return original.context();}
                    public MembershipIdentity identity(){return original.identity();}
                    public Map<String,Object> ballot(){return original.ballot();}
                    public Map<String,MembershipSourceExport.Content> references()throws IOException {if(constructor || references.incrementAndGet()>1)throw primary;return original.references();}
                    public byte[] read(String digest,long offset,int maximum)throws IOException {return original.read(digest,offset,maximum);}
                    public void close(){closes.incrementAndGet();original.close();throw cleanup;}
                };
            });
            var before=l.a.usage();
            var error=assertThrows(Exception.class,()->service.handle(l.reader.activationIdentity(),first.get()));
            // Always inspect the complete failed scope, even when the assertion
            // about the primary error fails on the original implementation.
            var close=assertThrows(IllegalStateException.class,service::close);
            assertSame(primary,error);assertTrue(V53SlotCloseDrainTest.contains(error,cleanup.getMessage()));
            assertSame(cleanup,close);assertSame(cleanup,assertThrows(IllegalStateException.class,service::close));
            assertEquals(1,closes.get());assertTrue(service.usage().closed());assertEquals(before,l.a.usage());
            assertEquals(2,budget.usage().leases(),"failed trace and parent remain charged");
        }
    }

}
