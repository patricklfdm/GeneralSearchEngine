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

/** Real framed handlers and original conditional files; routing bytes cannot
 * initialize these fixtures or replace final native/process qualification. */
class V53JoiningPreparationTest {
    @TempDir Path temp;
    V53JoiningRetentionNetworkTest.Local local()throws Exception {
        var helper=new V53JoiningRetentionNetworkTest();helper.temp=temp;return helper.new Local();
    }
    static MembershipJoiningRetentionCampaign.Hint hint(V53JoiningRetentionNetworkTest.Local l) {
        var c=l.in.current().context;var sources=new TreeMap<String,String>();
        for(var source:l.in.sources())sources.put(source.owner.nodeId().value(),source.basis.digest());
        return new MembershipJoiningRetentionCampaign.Hint(c.root,MembershipContext.cutDigest(c.cut),l.in.joining(),
                object(l.in.sources().getFirst().basis.value().get("ballot")),sources);
    }
    MembershipActivationEndpoint endpoint(V53JoiningRetentionNetworkTest.Local l)throws Exception {
        return new MembershipActivationEndpoint(l.source,l.a,bounds(),(p,q,k,d)->{throw new AssertionError("routing reads never send PREPARE");},
                l.fixture::verify,List.of(),List.of(),temp.resolve("endpoint-"+UUID.randomUUID()),l.clock::get,BUDGET);
    }
    MembershipJoiningPreparation publication(V53JoiningRetentionNetworkTest.Local l)throws Exception {
        return new MembershipJoiningPreparation(l.source,l.a,hint(l),()->{},l.clock::get,0,BUDGET);
    }
    @Test void routingReadUsesExistingEndpointAndExactTransportRetriesWithoutChangingOriginals()throws Exception {
        for(String drop:List.of("none","SOURCE_OFFER","CHUNK","TRANSFER_COMMIT"))try(var l=local()) {
            var files=V53ReplayFilesTest.files(l.path);var sourceUsage=l.a.usage();var receiverUsage=l.b.usage();
            try(var endpoint=endpoint(l);var publication=publication(l)) {
                endpoint.publishJoiningPreparation(publication);var dropped=new AtomicBoolean();var requests=new ArrayList<String>();
                try(var pull=l.pull((p,q,k,d)->{
                    assertEquals(l.source.activationIdentity(),p);assertEquals(BUDGET,d);requests.add(q.digest());
                    try{var response=endpoint.handle(l.reader.activationIdentity(),decode(q.bytes(),"wire",q.kind()));
                        if(k.equals(drop) && dropped.compareAndSet(false,true))return CompletableFuture.failedFuture(lost());
                        return CompletableFuture.completedFuture(decode(response.bytes(),"wire",response.kind()));
                    }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
                })) {
                    byte[] raw=pull.fetchPrefixMetadata(MembershipJoiningPreparation.reference(l.reader.activationContext(),l.reader.activationIdentity()),MembershipJoiningPreparation.MAXIMUM);
                    assertArrayEquals(MembershipJoiningPreparation.bytes(hint(l)),raw);
                    var received=MembershipJoiningPreparation.read(raw,l.reader.activationContext(),l.reader.activationIdentity(),l.source.activationIdentity());
                    assertEquals(hint(l),received);assertEquals(drop.equals("none")?0:1,requests.size()-new HashSet<>(requests).size());
                    assertThrows(IllegalArgumentException.class,()->new MembershipJoiningRetentionAcquisition(l.reader,l.b,bounds(),
                            (p,q,k,d)->{throw new AssertionError("hint cannot authorize a conditional owner");},()->{},l.clock::get,0,BUDGET,received));
                }
                assertEquals(files,V53ReplayFilesTest.files(l.path));assertTrue(l.source.originalSelection().isEmpty());
            }
            assertEquals(sourceUsage,l.a.usage());assertEquals(receiverUsage,l.b.usage());
        }
    }
    @Test void missingPublicationNeverFallsBackToSourceBytesOrASecondBallot()throws Exception {
        try(var l=local();var endpoint=endpoint(l);var pull=l.pull((p,q,k,d)->{
            try{return CompletableFuture.completedFuture(endpoint.handle(l.reader.activationIdentity(),q));}
            catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
        })) {
            var before=V53ReplayFilesTest.files(l.path);
            assertThrows(IllegalArgumentException.class,()->pull.fetchPrefixMetadata(MembershipJoiningPreparation.reference(l.reader.activationContext(),l.reader.activationIdentity()),MembershipJoiningPreparation.MAXIMUM));
            assertEquals(before,V53ReplayFilesTest.files(l.path));
        }
    }
    @Test void originalDeadlineHigherFenceAndRevocationStopAnOpenHintRead()throws Exception {
        for(String fault:List.of("deadline","fence","revoke"))try(var l=local();var endpoint=endpoint(l)) {
            var publisherClock=new AtomicLong();
            try(var publication=new MembershipJoiningPreparation(l.source,l.a,hint(l),()->{},publisherClock::get,0,BUDGET)) {
                endpoint.publishJoiningPreparation(publication);var changed=new AtomicBoolean();
                try(var pull=l.pull((p,q,k,d)->{
                    try{var response=endpoint.handle(l.reader.activationIdentity(),q);
                        if(k.equals("SOURCE_OFFER") && changed.compareAndSet(false,true))switch(fault) {
                            case "deadline"->publisherClock.set(BUDGET);
                            case "fence"->l.source.observeCurrent(l.in.fixture().source.ballot(21));
                            case "revoke"->endpoint.revokeJoiningPreparation(publication);
                        }
                        return CompletableFuture.completedFuture(response);
                    }catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
                })) {
                    assertThrows(Exception.class,()->pull.fetchPrefixMetadata(MembershipJoiningPreparation.reference(l.reader.activationContext(),l.reader.activationIdentity()),MembershipJoiningPreparation.MAXIMUM));
                    assertTrue(changed.get());
                }
            }
        }
    }
    @Test void endpointAcceptsOnlyItsActualOwnerAndOneLivePublication()throws Exception {
        try(var l=local();var endpoint=endpoint(l);var publication=publication(l)) {
            assertThrows(IllegalArgumentException.class,()->publication.belongsTo(l.reader,l.b));
            endpoint.publishJoiningPreparation(publication);
            assertThrows(IllegalArgumentException.class,()->endpoint.publishJoiningPreparation(publication));
            endpoint.revokeJoiningPreparation(publication);
            assertThrows(IllegalArgumentException.class,()->endpoint.publishJoiningPreparation(publication));
            try(var second=publication(l)){endpoint.publishJoiningPreparation(second);endpoint.close();assertThrows(IllegalArgumentException.class,()->second.belongsTo(l.source,l.a));}
        }
    }
    @Test void hintCodecRejectsWrongContextProposerSourcesAndNoncanonicalBytes()throws Exception {
        try(var l=local()) {
            var c=l.reader.activationContext();var expected=hint(l);byte[] raw=MembershipJoiningPreparation.bytes(expected);
            assertThrows(IllegalArgumentException.class,()->MembershipJoiningPreparation.read(raw,c,l.reader.activationIdentity(),V53DeclarationsTest.node(2)));
            for(String fault:List.of("root","cut","joining","ballot","minority","duplicate","extra","order","schema")) {
                var value=new TreeMap<>(object(parse(raw,MembershipJoiningPreparation.MAXIMUM)));
                switch(fault) {
                    case "root"->value.put("root","ff".repeat(32));case "cut"->value.put("cut","ff".repeat(32));
                    case "joining"->value.put("joining",MembershipBootstrapSeed.identity(V53DeclarationsTest.node(2)));
                    case "ballot"->{var ballot=new TreeMap<>(object(value.get("ballot")));ballot.put("proposer","node-2");value.put("ballot",ballot);}
                    case "minority"->value.put("sources",List.of(list(value.get("sources")).getFirst()));
                    case "duplicate"->{var rows=new ArrayList<Object>(list(value.get("sources")));rows.add(rows.getFirst());value.put("sources",rows);}
                    case "extra"->value.put("ready",true);
                    case "order"->{var rows=new ArrayList<>(list(value.get("sources")));Collections.reverse(rows);value.put("sources",rows);}
                    case "schema"->value.put("schema","other");
                }
                byte[] changed=canonical(value,MembershipJoiningPreparation.MAXIMUM);
                assertThrows(IllegalArgumentException.class,()->MembershipJoiningPreparation.read(changed,c,l.reader.activationIdentity(),l.source.activationIdentity()),fault);
            }
            assertThrows(IllegalArgumentException.class,()->MembershipJoiningPreparation.read(new byte[MembershipJoiningPreparation.MAXIMUM+1],c,l.reader.activationIdentity(),l.source.activationIdentity()));
        }
    }
    @Test void publicationRequiresItsExactLocalBasisAndPreservesAccountingOnFailure()throws Exception {
        try(var l=local()) {
            var original=hint(l);var changed=new TreeMap<>(original.sources());changed.put("node-1","ff".repeat(32));
            var before=l.a.usage();
            assertThrows(IllegalArgumentException.class,()->new MembershipJoiningPreparation(l.source,l.a,
                    new MembershipJoiningRetentionCampaign.Hint(original.root(),original.cut(),original.joining(),original.ballot(),changed),()->{},l.clock::get,0,BUDGET));
            assertEquals(before,l.a.usage());
        }
    }
    @Test void expiryReleasesThePublicationWithoutCreatingANewLifetime()throws Exception {
        try(var l=local()) {
            var before=l.a.usage();
            try(var publication=publication(l)) {
                assertTrue(publication.poll());assertEquals(before.leases()+1,l.a.usage().leases());
                l.clock.set(BUDGET);assertFalse(publication.poll());assertEquals(before,l.a.usage());
                l.clock.set(0);assertFalse(publication.poll());assertThrows(IllegalArgumentException.class,()->publication.belongsTo(l.source,l.a));
            }
        }
    }
}
