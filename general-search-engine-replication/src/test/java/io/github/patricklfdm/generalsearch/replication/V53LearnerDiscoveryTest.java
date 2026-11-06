package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;

/** Conditional byte/link fixtures only. Actual owner/TCP enrollment needs its own gate. */
class V53LearnerDiscoveryTest {
    static final long BUDGET=TimeUnit.SECONDS.toNanos(30);
    final class Fixture implements AutoCloseable {
        final V53CapsuleFixture fixture;
        final MembershipCapsule capsule;
        final MembershipLearnerRequest request;
        final MembershipIdentity peer;
        final MembershipResources resources;
        final AtomicLong clock=new AtomicLong();
        final List<Decoded> requests=new ArrayList<>();
        final List<Long> deadlines=new ArrayList<>();
        byte[] content;
        int chunk=71;
        Fixture(int size,String change,int cut) {this(size,change,cut,0);}
        Fixture(int size,String change,int cut,int observations) {
            resources=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,
                    MembershipResources.QUEUE_LIMIT,observations);
            fixture=new V53CapsuleFixture(size,change,cut);capsule=fixture.verify();content=fixture.source.root.bytes();
            var root=new MembershipRoot(new ReplicationGroupId(UUID.fromString((String)fixture.source.root.value().get("groupId"))),
                    UUID.fromString((String)fixture.source.root.value().get("historyId")),fixture.source.rootHash);
            var raw=object(list(fixture.state(2).get("results")).getFirst());var changeRequest=object(raw.get("request"));
            var target=list(changeRequest.get("target")).stream().map(MembershipFormat::object).map(MembershipContext::identity).toList();
            var joining=target.stream().filter(i->i.nodeId().value().equals("node-6")).findFirst().orElseThrow();
            request=new MembershipLearnerRequest(root,joining,new MembershipChangeRequest(new MembershipOperationId(root,1),
                    (String)changeRequest.get("expected"),MembershipChangeKind.valueOf(change),target),Path.of("/unused/learner"),Path.of("/unused/operation"));
            peer=target.getFirst();
        }
        Fixture(){this(3,"ADD",2);}
        MembershipLearnerDiscovery discover(MembershipSourcePull.Link link,ReplicationBounds bounds) {
            return new MembershipLearnerDiscovery(request,peer,resources,bounds,(p,r,k,d)->{requests.add(r);deadlines.add(d);return link.exchange(p,r,k,d);},
                    ()->{},clock::get,0,BUDGET);
        }
        MembershipLearnerDiscovery discover(MembershipSourcePull.Link link){return discover(link,V53TransferServiceTest.bound(2));}
        Decoded answer(Decoded request) {
            var payload=object(request.value().get("payload"));String kind;Map<String,Object> result;
            if(request.kind().equals("TRANSFER_COMMIT")){kind="TRANSFER_COMMIT";result=payload;}
            else if(number(request.value().get("sequence"))==1) {
                MembershipLearnerDiscovery.reservation(capsule.context,this.request.identity(),request);
                kind="SOURCE_OFFER";result=Map.of("id",payload.get("id"),"kind","RECORD","bytes",(long)content.length,"digest",hash(content));
            }else {
                int offset=Math.toIntExact(number(payload.get("offset")));byte[] part=Arrays.copyOfRange(content,offset,Math.min(content.length,offset+chunk));
                kind="CHUNK";result=Map.of("action","DATA","id",payload.get("id"),"offset",(long)offset,"bytes",Base64.getEncoder().encodeToString(part),"digest",hash(part));
            }
            return response(request,kind,result);
        }
        CompletableFuture<Decoded> normal(MembershipIdentity p,Decoded r,String k,long d){return CompletableFuture.completedFuture(answer(r));}
        @Override public void close(){assertEquals(0,resources.usage().leases());}
    }
    static Decoded response(Decoded request,String kind,Map<String,Object> payload) {
        var v=new TreeMap<>(request.value());v.put("sender",request.value().get("recipient"));v.put("recipient",request.value().get("sender"));v.put("payload",payload);
        return decode(encode("wire",kind,v),"wire",kind);
    }
    static MembershipTransport.Failure lost(){return new MembershipTransport.Failure(MembershipTransport.Reason.IO,"lost",null);}
    @Test void rootBytesComeFromChunkedOriginalAndDoNotConflateTheTwoDigests()throws Exception {
        try(var f=new Fixture();var pull=f.discover(f::normal)) {
            var root=pull.fetch();assertArrayEquals(f.content,root.bytes());assertNotEquals(root.digest(),root.rootDigest());
            assertEquals(1,f.requests.stream().filter(r->r.kind().equals("TRANSFER_COMMIT")).count());
            assertTrue(f.requests.size()>3);assertEquals(Set.of(BUDGET),new HashSet<>(f.deadlines));
            assertThrows(IllegalArgumentException.class,pull::fetch);
        }
    }
    @Test void activeReservationAcceptsOnlyTheExactJoiningMemberAcrossEveryAddReplaceProfile()throws Exception {
        for(int size:List.of(3,4,5))for(String kind:List.of("ADD","REPLACE")) {
            if(size==5 && kind.equals("ADD"))continue;
            for(int cut:List.of(2,3,4,5))try(var f=new Fixture(size,kind,cut);var pull=f.discover(f::normal)) {
                assertArrayEquals(f.content,pull.fetch().bytes());
            }
        }
    }
    @Test void absentJointCompletedAndRetiredReservationCannotStartLearnerDiscovery()throws Exception {
        for(int cut:List.of(0,1,6,7,8,9))try(var f=new Fixture(3,"ADD",cut);var pull=f.discover(f::normal)) {
            var e=assertThrows(IllegalArgumentException.class,pull::fetch);
            assertEquals("learner discovery active pre-joint reservation",e.getMessage());
        }
    }
    @Test void reservationAliasBindsTheFullRequestAndExactCorrelation()throws Exception {
        for(String mode:List.of("alias","sender","view","ballot","offset","sequence","bytes","action"))try(var f=new Fixture();var pull=f.discover((p,r,k,d)->{
            var v=new TreeMap<>(r.value());var payload=new TreeMap<>(object(v.get("payload")));
            switch(mode) {
                case "alias" -> payload.put("digest","a".repeat(64));
                case "sender" -> v.put("sender",MembershipBootstrapSeed.identity(f.peer));
                case "view" -> v.put("view","a".repeat(64));
                case "ballot" -> {var b=new TreeMap<>(object(v.get("ballot")));b.put("counter",2L);v.put("ballot",b);}
                case "offset" -> payload.put("offset",1L);
                case "sequence" -> v.put("sequence",2L);
                case "bytes" -> payload.put("bytes","YQ==");
                case "action" -> payload.put("action","ACK");
            }
            v.put("payload",payload);MembershipLearnerDiscovery.reservation(f.capsule.context,f.request.identity(),decode(encode("wire","CHUNK",v),"wire","CHUNK"));
            throw new AssertionError("changed request admitted");
        })) {assertThrows(IllegalArgumentException.class,pull::fetch);}
    }
    @Test void permanentIdentityDoesNotByItselfGrantLearnerEligibility()throws Exception {
        try(var f=new Fixture();var pull=f.discover((p,r,k,d)->{
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerDiscovery.reservation(f.capsule.context,f.peer,r));
            var joining=f.request.identity();var changed=new MembershipIdentity(joining.nodeId(),UUID.randomUUID(),joining.endpoint());
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerDiscovery.reservation(f.capsule.context,changed,r));
            return f.normal(p,r,k,d);
        })) {pull.fetch();}
    }
    @Test void transientRetriesPreserveOriginalFrameAndDeadline()throws Exception {
        try(var f=new Fixture()) {
            var count=new AtomicInteger();try(var pull=f.discover((p,r,k,d)->count.incrementAndGet()<3?CompletableFuture.failedFuture(lost()):f.normal(p,r,k,d))){pull.fetch();}
            assertEquals(1,f.requests.subList(0,3).stream().map(Decoded::digest).distinct().count());assertEquals(Set.of(BUDGET),new HashSet<>(f.deadlines));
        }
    }
    @Test void originalRootRequestReservationBindsExactBytesAcrossRetryAndFailure()throws Exception {
        for(boolean exhausted:List.of(false,true))try(var f=new Fixture(3,"ADD",2,1024)) {
            var attempts=new AtomicInteger();var owners=new HashMap<String,String>();
            try(var pull=f.discover((peer,request,kind,deadline)->{
                var live=new HashMap<String,MembershipResourceObservations.Charge>();
                for(var change:f.resources.observations().changes()) {
                    change.removed().forEach(c->live.remove(c.owner()));change.added().forEach(c->live.put(c.owner(),c));
                }
                var matching=live.values().stream().filter(c->c.owner().startsWith("source-request-"+request.digest()+"-")).toList();
                assertEquals(1,matching.size(),"ROOT discovery must retain the original request binding");
                var charge=matching.getFirst();assertEquals(MembershipResources.Unit.CONTROL,charge.unit());assertEquals(request.size(),charge.bytes());
                var previous=owners.putIfAbsent(request.digest(),charge.owner());if(previous!=null)assertEquals(previous,charge.owner());
                return exhausted || attempts.incrementAndGet()<3?CompletableFuture.failedFuture(lost()):f.normal(peer,request,kind,deadline);
            })) {
                if(exhausted)assertThrows(MembershipTransport.Failure.class,pull::fetch);
                else assertArrayEquals(f.content,pull.fetch().bytes());
            }
            assertEquals(3,Collections.frequency(f.requests.stream().map(Decoded::digest).toList(),f.requests.getFirst().digest()));
            assertEquals(f.requests.stream().map(Decoded::digest).distinct().count(),owners.size());
            assertEquals(Set.of(BUDGET),new HashSet<>(f.deadlines));assertEquals(0,f.resources.usage().leases());
        }
    }
    @Test void exhaustionAndPermanentFailuresStopWithinTheFrozenAttemptLimit()throws Exception {
        for(var reason:MembershipTransport.Reason.values())try(var f=new Fixture();var pull=f.discover((p,r,k,d)->
                CompletableFuture.failedFuture(new MembershipTransport.Failure(reason,"injected",null)))) {
            assertThrows(MembershipTransport.Failure.class,pull::fetch);
            assertEquals(Set.of(MembershipTransport.Reason.IO,MembershipTransport.Reason.DEADLINE).contains(reason)?3:1,f.requests.size());
        }
    }
    @Test void offerAndChunkCorruptionNeverReachCommit()throws Exception {
        for(String mode:List.of("oversized-offer","wrong-kind","wrong-id","empty-chunk","chunk-hash","chunk-offset","chunk-overflow","whole-digest"))
            try(var f=new Fixture();var pull=f.discover((p,r,k,d)->{
                var reply=f.answer(r);var payload=new TreeMap<>(object(reply.value().get("payload")));
                if(reply.kind().equals("SOURCE_OFFER")) {
                    switch(mode) {
                        case "oversized-offer" -> payload.put("bytes",16385L);
                        case "wrong-kind" -> payload.put("kind","CAPSULE");
                        case "wrong-id" -> payload.put("id",UUID.randomUUID().toString());
                        case "whole-digest" -> payload.put("digest","a".repeat(64));
                    }
                }else if(reply.kind().equals("CHUNK")) {
                    switch(mode) {
                        case "empty-chunk" -> payload.put("bytes","");
                        case "chunk-hash" -> payload.put("digest","b".repeat(64));
                        case "chunk-offset" -> payload.put("offset",number(payload.get("offset"))+1);
                        case "chunk-overflow" -> payload.put("bytes",Base64.getEncoder().encodeToString(new byte[16385]));
                    }
                }
                return CompletableFuture.completedFuture(response(r,reply.kind(),payload));
            })) {
                assertThrows(IllegalArgumentException.class,pull::fetch);
                assertFalse(f.requests.stream().anyMatch(r->r.kind().equals("TRANSFER_COMMIT")));
            }
    }
    @Test void wellFormedDifferentRootIsNotAcceptedEvenWithMatchingTransportEnvelope()throws Exception {
        try(var f=new Fixture()) {
            var value=new TreeMap<>(f.fixture.source.root.value());value.put("historyId",UUID.randomUUID().toString());f.content=encode("records","ROOT",value);
            try(var pull=f.discover(f::normal)) {
                assertEquals("learner discovery authentic ROOT identity",assertThrows(IllegalArgumentException.class,pull::fetch).getMessage());
                assertFalse(f.requests.stream().anyMatch(r->r.kind().equals("TRANSFER_COMMIT")));
            }
        }
    }
    @Test void closeDuringSubmissionCancelsThePendingFutureInsteadOfWaitingForBudget()throws Exception {
        try(var f=new Fixture()) {
            var ref=new AtomicReference<MembershipLearnerDiscovery>();var pending=new CompletableFuture<Decoded>();
            try(var pull=f.discover((p,r,k,d)->{ref.get().close();return pending;})) {
                ref.set(pull);assertThrows(java.io.IOException.class,pull::fetch);assertTrue(pending.isCancelled());
            }
        }
    }
    @Test void expiryDuringReplyCannotReturnRootOrStartAnotherAttempt()throws Exception {
        try(var f=new Fixture();var pull=f.discover((p,r,k,d)->{var reply=f.answer(r);f.clock.set(BUDGET);return CompletableFuture.completedFuture(reply);})){assertEquals("learner discovery original deadline",assertThrows(java.io.IOException.class,pull::fetch).getMessage());assertEquals(1,f.requests.size());}
    }
}
