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

/** Real conditional joint-generation stores and authenticated transfer service;
 * not a bootstrap/native transition qualification or maximum metadata test. */
class V53PendingFloorBorrowTest {
    @TempDir Path temp;
    final class Case {
        final Path path;
        final V53CurrentGenerationFixture fixture=new V53CurrentGenerationFixture(5,6,false);
        final List<MembershipFloor.Copy> copies=new ArrayList<>();
        final MembershipResources budget=resources();
        final Map<Integer,Path> paths=new TreeMap<>();
        final Decoded proposal;
        Case(String name)throws Exception {
            path=Files.createDirectory(temp.resolve(name));var helper=new V53FloorTest();
            for(int node:List.of(1,2,5,6)) {
                Path p=path.resolve("node-"+node);paths.put(node,p);copies.add(helper.copy(p,5,6,node));
            }
            proposal=MembershipFloor.create(fixture.root(),copies.getFirst(),copies);
            for(int i=0;i<copies.size();i++) {
                var smaller=new ArrayList<>(copies);smaller.remove(i);
                assertThrows(IllegalArgumentException.class,()->MembershipFloor.create(fixture.root(),copies.getFirst(),smaller));
            }
            var forced=new AtomicInteger();
            try(var owner=open(event->{if(event.equals("FLOOR_COPY_HANDED_OFF") && forced.incrementAndGet()==4)throw new IOException("cut before authority");})) {
                owner.prepareCurrent(fixture.fixture.source.ballot(20));owner.prepareCurrent(fixture.fixture.source.ballot(21));
                assertThrows(IOException.class,()->owner.establishFloor(copies,copy->{}));
            }
            assertEquals(0,budget.usage().leases());assertFalse(Files.exists(paths.get(1).resolve("floor-copies/floor.gsr")));
        }
        MembershipGrantJournal open(MembershipBallotAllocator.Cut cut)throws Exception {
            return MembershipGrantJournal.openFloors(paths.get(1),fixture.root(),V53DeclarationsTest.node(1),budget,fixture::verify,cut);
        }
        MembershipGrantJournal remote(int node,MembershipResources budget)throws Exception {
            return MembershipGrantJournal.openGenerations(paths.get(node),fixture.root(),V53DeclarationsTest.node(node),budget,fixture::verify,event->{});
        }
        void full(){assertEquals(6,budget.usage().counts().get(MembershipResources.Unit.SOURCE));assertEquals(7,budget.usage().counts().get(MembershipResources.Unit.APPLICATION));}
    }
    @Test void completeJointFloorReacquiresAllOriginalsAtSixSourcesAndSevenImages()throws Exception {
        var c=new Case("complete");var fresh=new ArrayList<MembershipFloor.Copy>();var running=new AtomicBoolean();
        try(var owner=c.open(event->{if(running.get())c.full();})) {
            running.set(true);c.full();assertTrue(owner.governingFloor().isEmpty());fresh.add(owner.floorCopyCurrent());
            for(int node:List.of(2,5,6)) {
                var remoteBudget=resources();var requests=new ArrayList<String>();
                try(var remote=c.remote(node,remoteBudget);
                    var service=MembershipTransferService.prefix(remote,remoteBudget,bounds(),()->{},()->0L,0,BUDGET)) {
                    var hint=new MembershipDiscovery.Hint(remote.activationIdentity(),remote.activationContext().cut,false);
                    MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                        try{c.full();assertEquals(BUDGET,deadline);var response=service.handle(owner.activationIdentity(),request);
                            requests.add(request.kind()+"->"+response.kind());return CompletableFuture.completedFuture(response);}
                        catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
                    };
                    try(var prefix=MembershipSourcePull.prefix(owner,hint,c.budget,bounds(),link,()->{},()->0L,0,BUDGET);
                        var generation=MembershipSourcePull.prefix(owner,hint,c.budget,bounds(),link,()->{},()->0L,0,BUDGET)) {
                        var original=c.copies.stream().filter(v->v.owner.nodeId().value().equals("node-"+node)).findFirst().orElseThrow();
                        prefix.fetchBorrowedFloorPrefix(owner.borrowPendingFloorPrefix(original.reference()).orElseThrow());
                        var copy=generation.fetchGeneration(prefix);assertEquals(original.reference(),copy.reference());
                        for(var file:original.copyFiles().entrySet())assertArrayEquals(file.getValue(),copy.fileBytes(file.getKey()));
                        owner.resumeFloorCopy(c.proposal,copy,()->{});fresh.add(copy);c.full();assertTrue(owner.governingFloor().isEmpty());
                        assertEquals(0,service.usage().live());
                    }
                    assertTrue(requests.containsAll(List.of("CHUNK->SOURCE_OFFER","CHUNK->CHUNK","TRANSFER_COMMIT->TRANSFER_COMMIT")));
                }
                assertEquals(0,remoteBudget.usage().leases());c.full();
            }
            owner.establishFloor(fresh,copy->{});assertArrayEquals(c.proposal.bytes(),owner.governingFloor().orElseThrow().bytes());c.full();
        }
        assertEquals(0,c.budget.usage().leases());
    }
    @Test void missingRemoteAndLostCommitNeverTurnStoredProposalIntoAuthority()throws Exception {
        for(String mode:List.of("unavailable","lost-commit","exhausted-commit","deadline","closed","higher","changed-packet")) {
            var c=new Case(mode);var clock=new AtomicLong();var count=new AtomicInteger();var lost=new AtomicBoolean();var calls=new ArrayList<String>();
            var remoteBudget=resources();var before=V53CombinedResourceRecoveryTest.disk(c.paths.get(1));
            try(var owner=c.open(event->{});var remote=c.remote(2,remoteBudget);
                var service=MembershipTransferService.prefix(remote,remoteBudget,bounds(),()->{},clock::get,0,BUDGET)) {
                var hint=new MembershipDiscovery.Hint(remote.activationIdentity(),remote.activationContext().cut,false);
                MembershipSourcePull.Link link=(peer,request,kind,deadline)->{
                    try {
                        c.full();count.incrementAndGet();calls.add(request.digest());
                        if(mode.equals("unavailable"))throw new MembershipTransport.Failure(MembershipTransport.Reason.IO,"missing owner",null);
                        var response=service.handle(owner.activationIdentity(),request);
                        if(mode.equals("changed-packet") && response.kind().equals("CHUNK")) {
                            var envelope=new TreeMap<>(response.value());var payload=new TreeMap<>(object(envelope.get("payload")));
                            byte[] bytes=Base64.getDecoder().decode((String)payload.get("bytes"));bytes[0]^=1;
                            payload.put("bytes",Base64.getEncoder().encodeToString(bytes));payload.put("digest",hash(bytes));envelope.put("payload",payload);
                            return CompletableFuture.completedFuture(decode(encode("wire","CHUNK",envelope),"wire","CHUNK"));
                        }
                        if(request.kind().equals("TRANSFER_COMMIT")) {
                            if(mode.equals("deadline"))clock.set(BUDGET);
                            if(mode.equals("higher"))owner.observeCurrent(c.fixture.fixture.source.ballot(22));
                            if(mode.equals("exhausted-commit") || mode.equals("lost-commit") && lost.compareAndSet(false,true))
                                throw new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost commit ACK",null);
                        }
                        return CompletableFuture.completedFuture(response);
                    }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
                };
                try(var prefix=MembershipSourcePull.prefix(owner,hint,c.budget,bounds(),link,()->{},clock::get,0,BUDGET)) {
                    var borrowed=owner.borrowPendingFloorPrefix(c.copies.get(1).reference()).orElseThrow();
                    assertThrows(IllegalArgumentException.class,prefix::verifiedPrefix,"stored bytes alone cannot authenticate a capsule");
                    if(mode.equals("closed"))borrowed.close();
                    if(mode.equals("lost-commit")) {
                        prefix.fetchBorrowedFloorPrefix(borrowed);assertEquals(1,calls.size()-new HashSet<>(calls).size());assertTrue(lost.get());
                    }else assertThrows(Exception.class,()->prefix.fetchBorrowedFloorPrefix(borrowed));
                    if(mode.equals("closed"))assertEquals(0,count.get());
                    if(mode.equals("unavailable"))assertEquals(3,count.get());
                    assertTrue(owner.governingFloor().isEmpty());c.full();
                }
                assertEquals(before,V53CombinedResourceRecoveryTest.disk(c.paths.get(1)));
            }
            assertEquals(0,c.budget.usage().leases());assertEquals(0,remoteBudget.usage().leases());
        }
    }
    @Test void borrowedOriginalCannotSurviveOwnerCloseOrInodeReplacement()throws Exception {
        for(boolean close:List.of(false,true)) {
            var c=new Case("lifetime-"+close);
            try(var owner=c.open(event->{})) {
                var borrowed=owner.borrowPendingFloorPrefix(c.copies.get(1).reference()).orElseThrow();
                if(close)owner.close();
                else {
                    Path file=c.paths.get(1).resolve("floor-copies/"+c.copies.get(1).generation.digest()+"/source.gscp");
                    Path replacement=c.path.resolve("replacement");Files.write(replacement,Files.readAllBytes(file));Files.move(replacement,file,StandardCopyOption.REPLACE_EXISTING);
                }
                assertThrows(IllegalArgumentException.class,borrowed::packet);borrowed.close();
            }
            assertEquals(0,c.budget.usage().leases());
        }
    }
    @Test void incompleteOriginalDoesNotGetBorrowedAndForeignReferenceIsRefused()throws Exception {
        for(String name:List.of("source.gscp","generation.gsr")) {
            var c=new Case("incomplete-"+name);Path packet=c.paths.get(1).resolve("floor-copies/"+c.copies.get(1).generation.digest()+"/"+name);
            byte[] bytes=Files.readAllBytes(packet);Files.write(packet,Arrays.copyOf(bytes,bytes.length/2));
            try(var owner=c.open(event->{})) {
                assertTrue(owner.borrowPendingFloorPrefix(c.copies.get(1).reference()).isEmpty());
                var ref=new TreeMap<>(c.copies.get(1).reference());ref.put("generation","00".repeat(32));
                assertThrows(IllegalArgumentException.class,()->owner.borrowPendingFloorPrefix(ref));assertTrue(owner.governingFloor().isEmpty());c.full();
            }
            assertEquals(0,c.budget.usage().leases());
        }
    }
    @Test void freshlyObservedSameCutReplacementCannotSubstituteForOriginalProposal()throws Exception {
        var c=new Case("replacement");Path source=c.paths.get(2),generation=source.resolve("generations/a/generation.gsr");
        var changed=new TreeMap<>(decode(Files.readAllBytes(generation),"records","GENERATION").value());changed.put("generation","b");
        byte[] bytes=encode("records","GENERATION",changed);Files.write(generation,bytes);
        Files.move(source.resolve("generations/a"),source.resolve("generations/b"));
        var selector=new TreeMap<>(decode(Files.readAllBytes(source.resolve("selector.gsr")),"records","SELECTOR").value());
        selector.put("generation","b");selector.put("digest",hash(bytes));Files.write(source.resolve("selector.gsr"),encode("records","SELECTOR",selector));
        var remoteBudget=resources();var before=V53CombinedResourceRecoveryTest.disk(c.paths.get(1));
        try(var owner=c.open(event->{});var remote=c.remote(2,remoteBudget);
            var service=MembershipTransferService.prefix(remote,remoteBudget,bounds(),()->{},()->0L,0,BUDGET)) {
            var hint=new MembershipDiscovery.Hint(remote.activationIdentity(),remote.activationContext().cut,false);
            MembershipSourcePull.Link link=(peer,request,kind,deadline)->{try{return CompletableFuture.completedFuture(service.handle(owner.activationIdentity(),request));}
                catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}};
            try(var prefix=MembershipSourcePull.prefix(owner,hint,c.budget,bounds(),link,()->{},()->0L,0,BUDGET);
                var copied=MembershipSourcePull.prefix(owner,hint,c.budget,bounds(),link,()->{},()->0L,0,BUDGET)) {
                prefix.fetchBorrowedFloorPrefix(owner.borrowPendingFloorPrefix(c.copies.get(1).reference()).orElseThrow());
                var replacement=copied.fetchGeneration(prefix);assertNotEquals(c.copies.get(1).reference(),replacement.reference());
                assertEquals("partial floor requires exact original copy",assertThrows(IllegalArgumentException.class,()->owner.resumeFloorCopy(c.proposal,replacement,()->{})).getMessage());
            }
        }
        assertEquals(before,V53CombinedResourceRecoveryTest.disk(c.paths.get(1)));
        assertEquals(0,c.budget.usage().leases());assertEquals(0,remoteBudget.usage().leases());
    }
}
