package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

class V53PrefixRecoveryTest {
    @TempDir Path temp;
    V53DiscoveryTest.Local local()throws Exception {
        var helper=new V53DiscoveryTest();helper.temp=Files.createDirectory(temp.resolve("local-"+UUID.randomUUID()));return helper.new Local();
    }
    MembershipPrefixRecovery recovery(V53DiscoveryTest.Local l,MembershipSourcePull.Link link)throws Exception {
        return new MembershipPrefixRecovery(l.owner,l.budget,bounds(),link,()->{},temp.resolve("scratch-"+UUID.randomUUID()),l.clock::get,0,BUDGET);
    }
    @Test void unchangedViewScansOnlyKnownIdentitiesWithoutDurableGrantOrScratch()throws Exception {
        try(var l=local()) {
            var files=l.files();var usage=l.budget.usage();var peers=new ArrayList<MembershipIdentity>();
            try(var work=recovery(l,(p,r,k,d)->{peers.add(p);assertEquals("STATUS_PROBE",r.kind());assertEquals(BUDGET,d);
                return CompletableFuture.completedFuture(MembershipDiscovery.answer(l.group.capsule.context,p,l.group.identities.getFirst(),r));})) {
                assertTrue(work.run().isEmpty());assertThrows(IllegalArgumentException.class,work::run);
            }
            assertEquals(l.group.identities.subList(1,3),peers);assertEquals(files,l.files());assertEquals(usage,l.budget.usage());assertTrue(l.events.isEmpty());
            try(var paths=Files.list(temp)){assertTrue(paths.noneMatch(p->p.getFileName().toString().startsWith("scratch-")));}
        }
    }
    @Test void exhaustedTransportMovesOnceToAnotherKnownPeerWithoutRenewingDeadline()throws Exception {
        try(var l=local()) {
            var attempts=new ArrayList<String>();var peers=new ArrayList<MembershipIdentity>();var files=l.files();
            try(var work=recovery(l,(p,r,k,d)->{peers.add(p);attempts.add(r.digest());assertEquals(BUDGET,d);l.clock.addAndGet(1);
                if(p.equals(l.peer()))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"offline",null));
                return CompletableFuture.completedFuture(MembershipDiscovery.answer(l.group.capsule.context,p,l.group.identities.getFirst(),r));})) {
                assertTrue(work.run().isEmpty());
            }
            assertEquals(4,peers.size());assertEquals(1,new HashSet<>(attempts.subList(0,3)).size());assertEquals(l.group.identities.get(2),peers.getLast());
            assertEquals(files,l.files());assertTrue(l.events.isEmpty());
        }
    }
    @Test void fatalTransportAndMalformedHintsStopBeforeAnotherPeerOrGrant()throws Exception {
        for(String mode:List.of("CAPACITY","PROTOCOL","CLOSED","conflicting-cut","unverified-new-view"))try(var l=local()) {
            var calls=new ArrayList<Decoded>();var files=l.files();
            try(var work=recovery(l,(p,r,k,d)->{
                calls.add(r);
                if(!mode.contains("-"))return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.valueOf(mode),mode,null));
                if(!r.kind().equals("STATUS_PROBE"))return CompletableFuture.completedFuture(V53ActivationDriverTest.reject(r,"INTEGRITY_FAILURE",false,false));
                var value=new TreeMap<>(l.response(r).value());var cut=new TreeMap<>(l.group.capsule.context.cut);
                if(mode.equals("conflicting-cut"))cut.put("entry","a".repeat(64));
                else {var view=new TreeMap<>(object(cut.get("view")));view.put("generation",1L);cut.put("view",view);cut.put("index",10L);}
                value.put("payload",Map.of("cut",cut,"ready",true,"nonce",object(r.value().get("payload")).get("nonce")));
                return CompletableFuture.completedFuture(decode(encode("wire","STATUS",value),"wire","STATUS"));
            })) {assertThrows(Exception.class,work::run);}
            assertEquals(mode.equals("unverified-new-view")?2:1,calls.size());assertEquals(files,l.files());assertTrue(l.events.isEmpty());
        }
    }
    @Test void higherBallotAndOriginalDeadlineRevokeDiscoveryBeforeActivation()throws Exception {
        for(boolean fence:List.of(false,true))try(var l=local()) {
            var calls=new AtomicInteger();
            try(var work=recovery(l,(p,r,k,d)->{calls.incrementAndGet();var reply=l.response(r);
                if(fence){var higher=new TreeMap<>(l.ballot);higher.put("counter",number(higher.get("counter"))+1);l.owner.observeCurrent(higher);}
                else l.clock.set(BUDGET);
                return CompletableFuture.completedFuture(reply);
            })) {
                if(fence)assertThrows(IllegalArgumentException.class,work::run);
                else assertEquals("discovery original deadline",assertThrows(IOException.class,work::run).getMessage());
            }
            assertEquals(1,calls.get());assertTrue(l.events.isEmpty());
        }
    }
    @Test void closeCancelsThePendingReadAndDrainsItsReservation()throws Exception {
        try(var l=local()) {
            var before=l.budget.usage();var entered=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            try(var work=recovery(l,(p,r,k,d)->{entered.countDown();return pending;});var executor=Executors.newVirtualThreadPerTaskExecutor()) {
                var running=executor.submit(work::run);assertTrue(entered.await(5,TimeUnit.SECONDS));work.close();
                assertThrows(ExecutionException.class,()->running.get(5,TimeUnit.SECONDS));assertTrue(pending.isCancelled());
            }
            assertEquals(before,l.budget.usage());assertTrue(l.events.isEmpty());
        }
    }
    @Test void electionDiscoveryConvertsOnlyDirectCleanPreAdoptionFencing()throws Exception {
        for(String mode:List.of("clean","suppressed","wrapped","deadline"))try(var l=local()) {
            var before=l.budget.usage();var files=l.files();
            try(var work=recovery(l,(p,r,k,d)->{
                var reply=l.response(r);
                if(mode.equals("deadline")){l.clock.set(BUDGET);return CompletableFuture.completedFuture(reply);}
                var higher=new TreeMap<>(l.ballot);higher.put("counter",number(higher.get("counter"))+1);l.owner.observeCurrent(higher);
                try{l.owner.checkActivationBallot(l.owner.activationContext().authority(),l.ballot);throw new AssertionError("missing fence");}
                catch(MembershipGrantJournal.HigherBallot lost) {
                    if(mode.equals("suppressed"))lost.addSuppressed(new IOException("failed original drain"));
                    return CompletableFuture.failedFuture(mode.equals("wrapped")?new IOException("unclassified wrapper",lost):lost);
                }catch(IOException error){return CompletableFuture.failedFuture(error);}
            })) {
                var failure=assertThrows(Exception.class,work::runForElection);
                if(mode.equals("clean"))assertInstanceOf(MembershipPrefixRecovery.Superseded.class,failure);
                else {
                    assertFalse(failure instanceof MembershipPrefixRecovery.Superseded);
                    if(mode.equals("suppressed"))assertEquals("failed original drain",failure.getSuppressed()[0].getMessage());
                }
            }
            assertEquals(files,l.files());assertEquals(before,l.budget.usage());assertTrue(l.events.isEmpty());
        }
    }
    @Test void actualAdoptionRequiresCompleteOriginalPrefixAndAncestry()throws Exception {
        // Historical forces are conditional fixtures. This exercises actual
        // exported bytes, retained-copy verification and durable adoption, not
        // complete native distributed transition qualification.
        for(int through:List.of(6,7))adoption(through,"normal");
    }
    @Test void durableAdoptionFailureCannotFallThroughToAnotherSource()throws Exception {adoption(7,"fail");}
    @Test void fencingAfterDurableAdoptionStartsCannotReturnToElectionWait()throws Exception {adoption(7,"fenced-election");}
    @Test void verifiedIncomingAdoptionBeforeLocalAdoptionReturnsToElectionWait()throws Exception {adoption(7,"external-adoption");}
    @Test void closeDrainsAnAdmittedAdoptionWithoutInterruptingItsForces()throws Exception {adoption(7,"close");}
    private void adoption(int through,String mode)throws Exception {
            var fixture=new V53AdoptionFenceFixture(3,through);Path server=temp.resolve("server-"+through),client=temp.resolve("client-"+through);
            fixture.provision(server);V53FloorWorker.provision(client,3,0,3);var a=resources();var b=resources();var events=new ArrayList<String>();
            var forced=new CountDownLatch(1);var resume=new CountDownLatch(1);
            var adopting=new AtomicReference<MembershipGrantJournal>();
            try(var remote=fixture.open(server,a,e->{});
                var owner=MembershipGrantJournal.openGenerations(client,fixture.initial.root(),V53DeclarationsTest.node(3),b,
                    (r,p,m)->MembershipCapsule.verify(r,p,m,fixture.owned),event->{
                        events.add(event);if(event.equals("ADOPTION_INSTALL_FENCED")) {
                            if(mode.equals("fail"))throw new IOException("injected durable adoption failure");
                            if(mode.equals("fenced-election")) {
                                var current=adopting.get();var state=current.discoveryState(b);var higher=new TreeMap<>(state.ballot());
                                higher.put("counter",number(higher.get("counter"))+1);current.observeCurrent(higher);
                                current.checkActivationBallot(state.context().authority(),state.ballot());
                            }
                            if(mode.equals("close")){forced.countDown();try{assertTrue(resume.await(10,TimeUnit.SECONDS));}
                                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("force interrupted",error);}
                                assertFalse(Thread.currentThread().isInterrupted());}
                        }
                    })) {
                adopting.set(owner);
                remote.adoptCurrent(fixture.remote.packet(),fixture.remote.source.images,List.of());var before=V53ReplayFilesTest.files(server);
                var calls=new ArrayList<String>();
                try(var service=MembershipTransferService.prefix(remote,a,bounds(),()->{},()->0L,0,BUDGET);
                    var work=new MembershipPrefixRecovery(owner,b,bounds(),(p,r,k,d)->{
                        calls.add(r.kind());assertEquals(remote.activationIdentity(),p);assertEquals(BUDGET,d);
                        try {
                            if(mode.equals("external-adoption") && calls.size()==1)owner.adoptCurrent(fixture.remote.packet(),fixture.remote.source.images,List.of());
                            return CompletableFuture.completedFuture(r.kind().equals("STATUS_PROBE")?remote.discoveryStatus(owner.activationIdentity(),r):service.handle(owner.activationIdentity(),r));
                        }
                        catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
                    },()->{},temp.resolve("adopt-scratch-"+through),()->0L,0,BUDGET)) {
                    if(mode.equals("fail"))assertEquals("injected durable adoption failure",assertThrows(IOException.class,work::run).getMessage());
                    else if(mode.equals("fenced-election"))assertThrows(MembershipGrantJournal.HigherBallot.class,work::runForElection);
                    else if(mode.equals("external-adoption")) {
                        assertThrows(MembershipPrefixRecovery.Superseded.class,work::runForElection);
                        assertEquals(1,calls.size());assertEquals(remote.activationContext().cut,owner.activationContext().cut);
                        assertTrue(events.contains("ADOPTION_INSTALL_BEFORE_RETURN"));
                    }
                    else {
                        if(mode.equals("close"))try(var executor=Executors.newVirtualThreadPerTaskExecutor()) {
                            var running=executor.submit(work::run);
                            try {
                                assertTrue(forced.await(10,TimeUnit.SECONDS));var closing=executor.submit(()->{work.close();return null;});
                                assertThrows(TimeoutException.class,()->closing.get(100,TimeUnit.MILLISECONDS));resume.countDown();
                                assertTrue(running.get(10,TimeUnit.SECONDS).isPresent());closing.get(10,TimeUnit.SECONDS);
                            }finally{resume.countDown();}
                        } else assertTrue(work.run().isPresent());
                        assertEquals(remote.activationContext().cut,owner.activationContext().cut);
                        assertEquals(through==6,owner.activationContext().voters().contains("node-3"));
                        assertTrue(events.contains("ADOPTION_INSTALL_BEFORE_RETURN"));
                    }
                    assertFalse(calls.contains("PREPARE"));assertEquals(!mode.equals("external-adoption"),calls.contains("CHUNK"));
                }
                assertEquals(before,V53ReplayFilesTest.files(server));
            }
            assertEquals(0,a.usage().leases());assertEquals(0,b.usage().leases());
    }
}
