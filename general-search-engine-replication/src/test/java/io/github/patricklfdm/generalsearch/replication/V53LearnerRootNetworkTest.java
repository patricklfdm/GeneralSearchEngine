package io.github.patricklfdm.generalsearch.replication;

import java.net.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Actual native RESERVE followed by first-contact ROOT retrieval. No learner
 * storage, readiness receipt, joint vote or public enrollment is claimed here. */
class V53LearnerRootNetworkTest {
    @TempDir Path temp;
    @Test void firstContactUsesTheForcedReservationAndNeverOpensALearnerListenerOrStore()throws Exception {
        discovery(false);
    }
    @Test void rootMetadataAndOriginalPrefixBorrowReleaseTogether()throws Exception {
        discovery(true);
    }
    private void discovery(boolean captureExports)throws Exception {
        var helper=new V53RoundDriverTest();helper.temp=temp;
        var nativeHelper=new V53NativeDispatchTest();nativeHelper.temp=temp;
        var n=nativeHelper.new Network(3,helper.controlBounds(),V53NativeDispatchTest.BUDGET,f->{},true,captureExports);
        List<Map<String,Object>> cases=List.of();boolean passed=false;
        if(captureExports)System.out.println("v53LearnerExportResources="+n.f.raw.toAbsolutePath());
        try(n) {
            try(var round=helper.driver(n,MembershipRoundDriver.Events.NONE)) {
                round.start();var original=n.owners.getFirst().activationContext();int port;
                try(var s=new ServerSocket(0,1,InetAddress.getByName("127.0.0.1"))){port=s.getLocalPort();}
                var joining=new MembershipIdentity(new ReplicationNodeId("node-4"),UUID.randomUUID(),new ReplicationEndpoint("127.0.0.1",port));
                assertFalse(original.identities.containsKey("node-4"));
                var targets=new ArrayList<MembershipIdentity>();for(var t:n.f.request.targets())targets.add(t.identity());targets.add(joining);
                var change=new MembershipChangeRequest(new MembershipOperationId(n.f.result.root(),1),original.authority(),MembershipChangeKind.ADD,targets);
                var learner=new MembershipLearnerRequest(n.f.result.root(),joining,change,temp.resolve("absent-learner"),temp.resolve("absent-learner-plan"));
                byte[] command=canonical(Map.of("request",MembershipLearnerDiscovery.request(change)),8192);
                Files.write(n.f.raw.resolve("learner-reserve-payload.bin"),command);round.submit("RESERVE",command);
                var originalOwner=n.owners.getFirst();var ownerBudget=n.resources.getFirst();
                var rootRequest=initial(learner,targets.getFirst());
                awaitNetworkIdle(n);
                // exportPrefix legitimately retires prior-generation borrows on
                // first access. Complete that maintenance before measuring the
                // exact delta of this test's six live exports.
                try(var prime=new MembershipLearnerRootExport(originalOwner,joining,rootRequest,ownerBudget,
                        System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {prime.references();}
                if(captureExports) {
                    byte[] originalRoot=originalOwner.activationCapsule().packet.objectBytes(originalOwner.activationContext().recordRootDigest());
                    cases=V53SpecialExportResources.probe(ownerBudget,List.of(clock->new MembershipLearnerRootExport(originalOwner,joining,
                            rootRequest,ownerBudget,clock::get,0,V53SpecialExportResources.BUDGET)),Map.of(hash(originalRoot),originalRoot));
                }
                // ROOT and complete-prefix reads share the original six-export
                // registry; rejection must release its attempted reservation.
                var borrows=new ArrayList<MembershipTransferExport>();
                int beforeLeases=ownerBudget.usage().leases();
                try {
                    var context=originalOwner.activationContext();
                    borrows.add(originalOwner.exportPrefix(MembershipContext.cutDigest(context.cut),
                            MembershipLearnerDiscovery.correlation(joining),change.expectedConfigurationDigest(),ownerBudget,
                            System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60)));
                    for(int i=0;i<5;i++)borrows.add(new MembershipLearnerRootExport(originalOwner,joining,rootRequest,ownerBudget,
                            System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60)));
                    int atLimit=ownerBudget.usage().leases();
                    var refusal=assertThrows(IllegalArgumentException.class,()->new MembershipLearnerRootExport(originalOwner,joining,
                            rootRequest,ownerBudget,System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60)));
                    assertEquals("prefix export owner capacity",refusal.getMessage());assertEquals(atLimit,ownerBudget.usage().leases());
                }finally{for(var borrow:borrows)borrow.close();}
                assertEquals(beforeLeases,ownerBudget.usage().leases());
                n.f.snapshot("before-learner-discovery");var wires=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
                var budget=new MembershipResources(512*MembershipResources.MIB);
                try(var contact=MembershipTransport.learner(learner,n.bounds,budget,(event,request,response)->{
                    if(event.equals("AFTER_RESPONSE_READ"))wires.add(V53SelectedPullTest.wire(request,response));
                })) {
                    // Binding the same endpoint succeeds: the contact client owns no server socket.
                    try(var unused=new ServerSocket(port,1,InetAddress.getByName("127.0.0.1"))) {
                        assertEquals(port,unused.getLocalPort());
                        for(int index:n.voters) {
                            var target=n.f.request.targets().get(index);
                            var before=V53ReplayFilesTest.files(target.replicaDirectory());
                            // Lose a real reply at the server boundary. The
                            // client must replay the same request; final-commit
                            // retry must not reopen the already released export.
                            n.drop.set(index==0?"SOURCE_OFFER":"TRANSFER_COMMIT");
                            try(var pull=new MembershipLearnerDiscovery(learner,target.identity(),budget,n.bounds,contact::exchange,()->{},
                                    System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
                                assertArrayEquals(Files.readAllBytes(target.replicaDirectory().resolve("root.gsr")),pull.fetch().bytes());
                            }
                            assertEquals("",n.drop.get());
                            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));
                        }
                    }
                    assertFalse(Files.exists(learner.replicaDirectory()));assertFalse(Files.exists(learner.operationDirectory()));
                    n.f.snapshot("after-learner-discovery");
                    var peer=targets.getFirst();var forbidden=decode(encode("wire","PREPARE",Map.of("root",learner.root().manifestDigest(),
                            "view",change.expectedConfigurationDigest(),"sender",MembershipBootstrapSeed.identity(joining),"recipient",MembershipBootstrapSeed.identity(peer),
                            "ballot",MembershipLearnerDiscovery.correlation(joining),"trace",UUID.randomUUID().toString(),"sequence",1L,
                            "payload",Map.of("promise","a".repeat(64)))),"wire","PREPARE");
                    assertEquals(MembershipTransport.Reason.PROTOCOL,V53MembershipTransportTest.failure(contact.exchange(peer,forbidden,"PROMISE",
                            System.nanoTime()+TimeUnit.SECONDS.toNanos(10))).reason);
                    assertThrows(IllegalArgumentException.class,()->contact.learn(n.owners.getFirst().activationCapsule()));
                    try(var obsolete=new MembershipLearnerRootExport(originalOwner,joining,rootRequest,ownerBudget,
                            System::nanoTime,System.nanoTime(),TimeUnit.SECONDS.toNanos(180))) {
                        round.submit("CANCEL",canonical(Map.of("number",1L),8192));
                        assertThrows(IllegalArgumentException.class,obsolete::references);
                    }
                    try(var rejected=new MembershipLearnerDiscovery(learner,peer,budget,n.bounds,contact::exchange,()->{},System::nanoTime,
                            System.nanoTime(),TimeUnit.SECONDS.toNanos(60))) {
                        assertThrows(java.io.IOException.class,rejected::fetch);
                    }
                }
                assertEquals(0,budget.usage().leases());
                Files.write(n.f.raw.resolve("learner-root-wire.json"),canonical(wires,1024*1024));
                Files.write(n.f.raw.resolve("learner-root-result.json"),canonical(Map.of("status","PASS","scope","native-reservation-root-discovery", 
                        "voter",false,"materialized",false,"publicReady",false,"phase3Complete",false),4096));
                passed=true;
            }
        }catch(Throwable failure){passed=false;throw failure;}
        finally{if(captureExports)V53SpecialExportResources.save(n.f.raw,"learner-root",cases,n.resources.getFirst(),passed);}
    }
    private static Decoded initial(MembershipLearnerRequest learner,MembershipIdentity peer) {
        return decode(encode("wire","CHUNK",Map.of("root",learner.root().manifestDigest(),"view",learner.change().expectedConfigurationDigest(),
                "sender",MembershipBootstrapSeed.identity(learner.identity()),"recipient",MembershipBootstrapSeed.identity(peer),
                "ballot",MembershipLearnerDiscovery.correlation(learner.identity()),"trace",UUID.randomUUID().toString(),"sequence",1L,
                "payload",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest",MembershipLearnerDiscovery.reference(learner),"bytes",""))),"wire","CHUNK");
    }
    private static void awaitNetworkIdle(V53NativeDispatchTest.Network network)throws Exception {
        long limit=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
        for(;;) {
            boolean idle=network.transports.stream().allMatch(t->{var u=t.usage();return u.outgoing()==0 && u.incoming()==0 && u.sockets()==0;})
                    && network.endpoints.stream().allMatch(e->{var u=e.usage();return u.waiters()==0 && u.pendingExchanges()==0 && !u.controlRunning();});
            if(idle)return;
            assertTrue(System.nanoTime()<limit,"native I/O must drain before exact resource accounting");Thread.sleep(10);
        }
    }
}
