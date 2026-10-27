package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

class V53PendingCheckpointExportTest {
    @TempDir Path temp;
    static final long BUDGET=TimeUnit.SECONDS.toNanos(90);
    @Test void actualPendingAckCrossesTcpAndSuppliesNativePublication()throws Exception {
        var helper=new V53FutureRetentionEndpointTest();helper.temp=temp;
        try(var group=helper.new Group(3,true)) {
            var local=group.owners.getFirst();var applied=group.applied.getFirst();var statement=applied.plan().statement;
            var services=new ArrayList<MembershipTransferService>();var transports=new ArrayList<MembershipTransport>();
            var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
            try {
                for(int i=0;i<3;i++) {
                    var owner=group.owners.get(i);var bounds=ReplicationBounds.defaults();
                    var service=new MembershipTransferService(owner,group.fixture.ballot,group.budgets.get(i),bounds,
                            ()->owner.checkActivationBallot(owner.activationContext().authority(),group.fixture.ballot),
                            System::nanoTime,System.nanoTime(),BUDGET);services.add(service);
                    transports.add(new MembershipTransport(owner.activationCapsule(),owner.activationIdentity(),bounds,group.budgets.get(i),service,
                            (event,request,response)->{if(event.equals("BEFORE_RESPONSE_WRITE"))wire.add(V53SelectedPullTest.wire(request,response));}));
                }
                var acknowledgements=new ArrayList<Decoded>();acknowledgements.add(applied.endorsement().acknowledgement());
                var owned=new HashSet<MembershipContext.Owned>();owned.add(applied.endorsement().owned());
                for(int i=1;i<3;i++) {
                    var source=group.owners.get(i).activationIdentity();
                    var expected=decode(encode("records","CHECKPOINT_ACK",Map.of("root",statement.value().get("root"),"voter",source.nodeId().value(),
                            "incarnation",source.storageId().toString(),"cut",statement.value().get("end"),"statement",statement.digest())),"records","CHECKPOINT_ACK");
                    try(var pull=new MembershipSourcePull(local.activationCapsule(),local.activationIdentity(),source,group.fixture.ballot,UUID.randomUUID(),
                            group.budgets.getFirst(),ReplicationBounds.defaults(),transports.getFirst()::exchange,
                            ()->local.checkActivationBallot(local.activationContext().authority(),group.fixture.ballot),System::nanoTime,System.nanoTime(),BUDGET)) {
                        var received=pull.fetchCheckpointAcknowledgement(statement,expected);
                        assertArrayEquals(expected.bytes(),received.acknowledgement().bytes());acknowledgements.add(received.acknowledgement());owned.add(received.owned());
                        group.timeline.add(Map.of("node",source.nodeId().value(),"event","PENDING_CHECKPOINT_ACK_RECEIVED","digest",received.acknowledgement().digest()));
                    }
                }
                local.publishCurrent(applied,acknowledgements,owned,List.of());
                assertEquals(1L,local.activationContext().cut.get("index"));
                for(var owner:group.owners.subList(1,3))assertEquals(0L,owner.activationContext().cut.get("index"));
                group.fixture.snapshot("after-checkpoint-publication");
                Files.write(group.fixture.raw.resolve("checkpoint-result.json"),canonical(Map.of("status","PASS","published","node-1",
                        "statement",statement.digest(),"acknowledgements",acknowledgements.stream().map(Decoded::digest).toList()),65536));
            }finally {
                for(var transport:transports)transport.close();for(var service:services)service.close();
                Files.write(group.fixture.raw.resolve("checkpoint-wire.json"),canonical(wire,1024*1024));
            }
        }
    }
    @Test void nativeExportNeedsLiveReapplicationAndFencesWithItsOwner()throws Exception {
        var helper=new V53FutureRetentionEndpointTest();helper.temp=temp;
        try(var group=helper.new Group(3,true)) {
            var target=group.fixture.request.targets().get(1);var prior=group.applied.get(1);var ack=prior.endorsement().acknowledgement();
            group.owners.get(1).close();var budget=group.budgets.get(1);
            try(var owner=MembershipGrantJournal.openRetainingFuturePeers(target.replicaDirectory(),target.materialization().directory(),group.fixture.result.root(),
                    target.identity(),budget,MembershipGrantJournal.MAXIMUM,event->{})) {
                assertThrows(IllegalArgumentException.class,()->owner.exportRecord(ack.digest(),"CHECKPOINT_ACK",group.fixture.ballot,System::nanoTime,System.nanoTime(),BUDGET));
                var current=owner.applyCurrent(builder().configuration(),target.materialization());assertArrayEquals(ack.bytes(),current.endorsement().acknowledgement().bytes());
                try(var export=owner.exportRecord(ack.digest(),"CHECKPOINT_ACK",group.fixture.ballot,System::nanoTime,System.nanoTime(),BUDGET)) {
                    assertArrayEquals(ack.bytes(),export.read(ack.digest(),0,4096));
                    owner.observeCurrent(Map.of("counter",3L,"proposer","node-1","incarnation",group.owners.getFirst().activationIdentity().storageId().toString()));
                    assertThrows(IllegalArgumentException.class,()->export.read(ack.digest(),0,4096));
                }
                assertEquals(0,budget.usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0));
            }
        }
    }
    @Test void pendingStatementAndAckAreOwnExactBytesAndBorrowExpires()throws Exception {
        var helper=new V53FutureRetentionEndpointTest();helper.temp=temp;
        try(var group=helper.new Group(3,true)) {
            var owner=group.owners.get(1);var end=group.applied.get(1);var clock=new java.util.concurrent.atomic.AtomicLong();
            for(var record:List.of(end.plan().statement,end.endorsement().acknowledgement())) {
                clock.set(0);
                try(var export=owner.exportRecord(record.digest(),record.kind(),group.fixture.ballot,clock::get,0,BUDGET)) {
                    assertArrayEquals(record.bytes(),export.read(record.digest(),0,32768));clock.set(BUDGET);
                    assertThrows(IllegalArgumentException.class,export::references);
                }
            }
            var foreign=group.applied.getFirst().endorsement().acknowledgement();
            assertThrows(IllegalArgumentException.class,()->owner.exportRecord(foreign.digest(),"CHECKPOINT_ACK",group.fixture.ballot,System::nanoTime,System.nanoTime(),BUDGET));
            assertEquals(0,group.budgets.get(1).usage().counts().getOrDefault(MembershipResources.Unit.CONTROL,0));
        }
    }
}
