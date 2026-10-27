package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import java.nio.file.Path;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53NativeVotingLimitsTest {
    @TempDir Path temp;
    @Test void exactTransportRetriesStopAtThreeAndKeepOriginalDeadlineAndNoVote()throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false)) {
            var clock=new AtomicLong();var requests=new ArrayList<String>();var deadlines=new ArrayList<Long>();var budget=n.budgets.get(1);int held=budget.usage().leases();
            try(var endpoint=new MembershipVotingEndpoint(n.owners.get(1),budget,ReplicationBounds.defaults(),(peer,request,kind,deadline)->{
                requests.add(request.digest());deadlines.add(deadline);return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"original source unavailable",null));
            },clock::get,0,V53NativeVotingTest.BUDGET)) {
                var request=n.request(1,n.accept);var before=V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory());
                assertThrows(MembershipTransport.Failure.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),request));
                assertEquals(3,requests.size());assertEquals(1,requests.stream().distinct().count());assertEquals(List.of(V53NativeVotingTest.BUDGET,V53NativeVotingTest.BUDGET,V53NativeVotingTest.BUDGET),deadlines);
                assertThrows(MembershipTransport.Failure.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),request));assertEquals(3,requests.size());
                assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory()));
                clock.set(V53NativeVotingTest.BUDGET);assertFalse(endpoint.poll());assertThrows(IllegalArgumentException.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),request));
            }
            assertEquals(held,budget.usage().leases());assertEquals(0,budget.usage().counts().getOrDefault(MembershipResources.Unit.WAITER,0));
        }
    }
    @Test void alteredPayloadFailsBeforeAnyAcceptanceEvenWithValidChunkHash()throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,true)) {
            var changed=new AtomicBoolean();var owner=n.owners.get(1);var before=V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory());
            try(var endpoint=new MembershipVotingEndpoint(owner,n.budgets.get(1),ReplicationBounds.defaults(),(peer,request,kind,deadline)->
                n.transports.get(1).exchange(peer,request,kind,deadline).thenApply(response->{
                    if(response.kind().equals("CHUNK") && object(request.value().get("payload")).get("digest").equals(n.entry.value().get("payload"))) {
                        var payload=new TreeMap<>(object(response.value().get("payload")));byte[] bytes=Base64.getDecoder().decode((String)payload.get("bytes"));bytes[bytes.length-1]^=1;
                        payload.put("bytes",Base64.getEncoder().encodeToString(bytes));payload.put("digest",hash(bytes));var value=new TreeMap<>(response.value());value.put("payload",payload);changed.set(true);
                        return decode(encode("wire","CHUNK",value),"wire","CHUNK");
                    }return response;
                }),System::nanoTime,System.nanoTime(),V53NativeVotingTest.BUDGET)) {
                var error=assertThrows(IllegalArgumentException.class,()->endpoint.handle(n.owners.getFirst().activationIdentity(),n.request(1,n.accept)));
                assertTrue(error.getMessage().contains("metadata digest"),error.getMessage());assertTrue(changed.get());
            }
            assertTrue(owner.voting(n.budgets.get(1)).record("ACCEPT").isEmpty());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(1).replicaDirectory()));
        }
    }
    @Test void proofCannotCountAnUnreachableOriginalVoterFromTheProposersProofAlone()throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false)) {
            for(int i=1;i<3;i++)n.send(i,n.request(i,n.accept));var proof=n.proof();n.endpoints.get(1).close();
            var before=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());
            assertThrows(ExecutionException.class,()->n.send(2,n.request(2,proof)));
            assertTrue(n.owners.get(2).voting(n.budgets.get(2)).record("PROOF").isEmpty());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
        }
    }
    @Test void foreignProposerAndUnpromisedBallotNeverReachTheNetwork()throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false)) {
            var owner=n.owners.get(2);var sender=n.owners.getFirst().activationIdentity();var before=V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory());n.noOutgoing.set(true);
            var request=n.request(2,n.accept);var changed=new TreeMap<>(request.value());changed.put("sender",MembershipBootstrapSeed.identity(n.owners.get(1).activationIdentity()));
            var foreign=decode(encode("wire","ACCEPT",changed),"wire","ACCEPT");
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(2).handle(n.owners.get(1).activationIdentity(),foreign));
            changed=new TreeMap<>(request.value());changed.put("ballot",Map.of("counter",3L,"proposer","node-1","incarnation",sender.storageId().toString()));
            var unpromised=decode(encode("wire","ACCEPT",changed),"wire","ACCEPT");
            assertThrows(IllegalArgumentException.class,()->n.endpoints.get(2).handle(sender,unpromised));
            assertTrue(owner.voting(n.budgets.get(2)).record("ACCEPT").isEmpty());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().get(2).replicaDirectory()));
        }
    }
    @Test void originalReceiptUsesItsOwnLookupNamespaceAndContentDigest()throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false)) {
            var owner=n.owners.getFirst();var context=owner.activationContext();byte[] receipt=MembershipVoteReceipt.bytes(context,owner.activationIdentity(),n.accept);
            String digest=hash(receipt),reference=MembershipVoteReceipt.reference(receipt);assertNotEquals(digest,reference);var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            assertThrows(IllegalArgumentException.class,()->owner.exportTransfer(digest,context.authority(),n.f.ballot,System::nanoTime,System.nanoTime(),V53NativeVotingTest.BUDGET));
            try(var exported=owner.exportTransfer(reference,context.authority(),n.f.ballot,System::nanoTime,System.nanoTime(),V53NativeVotingTest.BUDGET)) {
                assertEquals(Set.of(reference),exported.references().keySet());assertEquals(digest,exported.references().get(reference).digest());
                assertArrayEquals(receipt,exported.read(digest,0,2048));assertThrows(IllegalArgumentException.class,()->exported.read(reference,0,2048));
            }
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
        }
    }
    @Test void carriedOriginalVoteCannotAcknowledgeANewInstalledRound()throws Exception {
        var helper=new V53NativeVotingTest();helper.temp=temp;
        try(var n=helper.new Network(3,false)) {
            for(var endpoint:n.endpoints)endpoint.close();for(var transport:n.transports)transport.close();
            var proposer=n.owners.get(1);var ballot=Map.<String,Object>of("counter",proposer.reserveCounter(),"proposer",proposer.activationIdentity().nodeId().value(),
                    "incarnation",proposer.activationIdentity().storageId().toString());
            var offers=new ArrayList<MembershipSelection.Source>();var images=new TreeMap<String,byte[]>();
            for(int i=0;i<3;i++) {
                var owner=n.owners.get(i);owner.prepareCurrent(ballot);var source=owner.originalSource();offers.add(source);
                Path stored=n.f.request.targets().get(i).replicaDirectory().resolve("sources/"+source.basis.value().get("basisId"));
                for(String digest:source.capsule.packet.images().keySet())images.put(digest,java.nio.file.Files.readAllBytes(stored.resolve(digest+".image")));
            }
            for(var owner:n.owners)owner.selectCurrent(offers,List.of());
            for(var owner:n.owners)owner.installCurrent(offers,List.of(),List.of(),images);
            var owner=n.owners.getFirst();var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            var original=MembershipPendingAccept.decode(java.nio.file.Files.readAllBytes(n.f.request.targets().getFirst().replicaDirectory().resolve("pending.accept")));
            assertNotNull(original);assertEquals(n.accept.digest(),original.accept().digest());assertNotEquals(ballot,original.accept().value().get("ballot"));
            var scope=owner.voting(n.budgets.getFirst());assertTrue(scope.record("ACCEPT").isEmpty());assertThrows(IllegalArgumentException.class,()->scope.observation(n.accept));
            var request=MembershipActivation.frame("ACCEPT",owner.activationContext(),proposer.activationIdentity(),owner.activationIdentity(),ballot,UUID.randomUUID(),1,Map.of("acceptance",n.accept.digest()));
            assertTrue(scope.acknowledge(proposer.activationIdentity(),request).isEmpty());assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
        }
    }
}
