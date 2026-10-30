package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53NativeCampaignFenceTest {
    @TempDir Path temp;
    @Test void initialGrantCapacityWaitsWithoutSubmittingPromiseThenUsesFreshOriginalRound()throws Exception {
        var fixture=new V53NativeDispatchTest();fixture.temp=temp;
        try(var n=fixture.new Network()) {
            var owner=n.owners.getFirst();var resources=n.resources.getFirst();var held=new ArrayList<MembershipResources.Lease>();
            var node=n.f.request.targets().getFirst().replicaDirectory();var before=V53ReplayFilesTest.files(node);long began=System.nanoTime();
            try {
                while(resources.usage().counts().getOrDefault(MembershipResources.Unit.APPLICATION,0)<MembershipResources.Unit.APPLICATION.count)
                    held.add(resources.reserve(MembershipResources.Unit.APPLICATION,"other-copy-"+held.size(),1));
                try(var driver=new MembershipActivationDriver(owner,n.endpoints.getFirst(),resources,n.bounds,(p,r,k,d)->{
                        throw new AssertionError("capacity admission must not send a grant");
                    },List.of(),List.of(),temp.resolve("capacity-campaign"),System::nanoTime,V53NativeDispatchTest.BUDGET,3)) {
                    var lost=assertThrows(MembershipCampaignLost.class,()->driver.run(began));
                    assertEquals(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,lost.reason);
                    var cause=assertInstanceOf(MembershipOperationException.class,lost.getCause());
                    assertEquals(MembershipOperationException.Reason.CAPACITY_EXCEEDED,cause.reason());
                    assertEquals(AutomaticReplicationException.Outcome.NOT_SUBMITTED,cause.outcome());
                    assertEquals(0,driver.campaigns());
                }
                var after=V53ReplayFilesTest.files(node);
                assertNotEquals(before.get("allocator.gsr"),after.get("allocator.gsr"),"failed reservation still burns its original ballot counter");
                var unchanged=new TreeMap<>(after);unchanged.put("allocator.gsr",before.get("allocator.gsr"));assertEquals(before,unchanged);
            }finally{for(var lease:held)lease.close();}
            n.activate();assertEquals(3L,n.ballot.get("counter"));
        }
    }
    @Test void onlyDirectTransportAvailabilityWithoutCleanupFailurePermitsFreshRecovery() {
        for(var reason:MembershipTransport.Reason.values()) {
            var failure=new MembershipTransport.Failure(reason,"transport test",null);
            var actual=assertThrows(IOException.class,()->MembershipRoundDriver.campaignCall(()->{throw failure;}));
            if(reason==MembershipTransport.Reason.IO || reason==MembershipTransport.Reason.DEADLINE) {
                assertEquals(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,assertInstanceOf(MembershipCampaignLost.class,actual).reason);
                assertSame(failure,actual.getCause());
            }else assertSame(failure,actual);
            var wrapper=new IOException("application failure",failure);
            assertSame(wrapper,assertThrows(IOException.class,()->MembershipRoundDriver.campaignCall(()->{throw wrapper;})));
            failure.addSuppressed(new IOException("cleanup failure"));
            assertSame(failure,assertThrows(IOException.class,()->MembershipRoundDriver.campaignCall(()->{throw failure;})));
        }
    }
    @Test void obsoleteNativeAcceptReturnsOriginalHigherPromiseAndCancelsSender()throws Exception {
        var fixture=new V53NativeDispatchTest();fixture.temp=temp;
        try(var n=fixture.new Network()) {
            n.activate();var accept=n.begin(false);var request=n.request(1,"ACCEPT",Map.of("acceptance",accept.digest()));
            var target=n.owners.get(1);var next=new TreeMap<>(n.ballot);next.put("counter",number(next.get("counter"))+1);
            target.prepareCurrent(next);var before=V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory());
            var response=n.endpoints.get(1).handle(n.owners.getFirst().activationIdentity(),request);
            MembershipWire.correlated(request,response,"ACCEPT_ACK");assertEquals("REJECT",response.kind());
            assertEquals(Map.of("reason","STALE_EPOCH","promised",next),response.value().get("payload"));
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(1).handle(n.owners.get(2).activationIdentity(),request));
            for(var kind:List.of("PREPARE","SELECTED","PROOF","APPLY")) {
                Map<String,Object> payload=switch(kind) {
                    case "PREPARE" -> Map.of("promise",n.owners.getFirst().promised().orElseThrow().digest());
                    case "SELECTED" -> Map.of("selection",n.selected.digest());
                    case "PROOF" -> Map.of("proof","0".repeat(64));
                    default -> Map.of("certificate","0".repeat(64),"selection",n.selected.digest());
                };
                var old=n.request(1,kind,payload);var rejected=n.endpoints.get(1).handle(n.owners.getFirst().activationIdentity(),old);
                assertEquals(response.value().get("payload"),rejected.value().get("payload"));
                assertEquals(old.value().get("trace"),rejected.value().get("trace"));assertEquals(old.value().get("ballot"),rejected.value().get("ballot"));
            }
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory()));
            var error=assertThrows(MembershipCampaignLost.class,()->MembershipRoundDriver.campaignCall(()->
                MembershipSlotDelivery.deliver(n.owners.getFirst(),target.activationIdentity(),request,n.resources.getFirst(),n.transports.getFirst(),
                    System::nanoTime,System.nanoTime(),V53NativeDispatchTest.BUDGET)));
            assertEquals(MembershipCampaignLost.Reason.HIGHER_BALLOT,error.reason);
            assertEquals(n.ballot,n.owners.getFirst().promised().orElseThrow().value().get("ballot"),"negative reply must not grant locally");
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory()));
            assertEquals(1,n.wire.stream().filter(row->MembershipWire.decode(Base64.getDecoder().decode((String)row.get("request")),FRAME).digest().equals(request.digest())).count());
        }
    }
    @Test void originalHigherGrantCancelsOldVotingWithoutHidingPhysicalCorruption()throws Exception {
        var fixture=new V53NativeDispatchTest();fixture.temp=temp;
        try(var n=fixture.new Network()) {
            n.activate();var owner=n.owners.getFirst();var voting=owner.voting(n.resources.getFirst());
            var basis=owner.originalBasis().orElseThrow();var next=new TreeMap<>(voting.ballot);
            next.put("counter",number(next.get("counter"))+1);owner.prepareCurrent(next);
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            var error=assertThrows(MembershipCampaignLost.class,()->MembershipRoundDriver.campaignCall(()->{voting.check();return null;}));
            assertEquals(MembershipCampaignLost.Reason.HIGHER_BALLOT,error.reason);
            assertInstanceOf(MembershipGrantJournal.HigherBallot.class,error.getCause());
            assertThrows(MembershipCampaignLost.class,()->MembershipRoundDriver.campaignCall(()->{owner.checkActivation(basis,null,false);return null;}));
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            Path selector=n.f.request.targets().getFirst().replicaDirectory().resolve("selector.gsr");byte[] original=Files.readAllBytes(selector);
            try {
                var corrupt=original.clone();corrupt[corrupt.length-1]^=1;Files.write(selector,corrupt);
                var invalid=assertThrows(Exception.class,()->MembershipRoundDriver.campaignCall(()->{voting.check();return null;}));
                assertFalse(invalid instanceof MembershipCampaignLost);assertFalse(invalid instanceof MembershipGrantJournal.HigherBallot);
            }finally{Files.write(selector,original);}
            var fenced=assertThrows(MembershipGrantJournal.HigherBallot.class,voting::check);
            var wrapped=new IOException("invalid original response",fenced);
            assertSame(wrapped,assertThrows(IOException.class,()->MembershipRoundDriver.campaignCall(()->{throw wrapped;})));
            var arbitrary=new IllegalArgumentException(fenced.getMessage());
            assertSame(arbitrary,assertThrows(IllegalArgumentException.class,()->MembershipRoundDriver.campaignCall(()->{throw arbitrary;})));
            fenced.addSuppressed(new IOException("drain failed"));
            assertSame(fenced,assertThrows(MembershipGrantJournal.HigherBallot.class,()->MembershipRoundDriver.campaignCall(()->{throw fenced;})));
        }
    }
}
