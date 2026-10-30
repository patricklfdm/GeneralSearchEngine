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
import static io.github.patricklfdm.generalsearch.admission.OfflineApplication.*;

/** Conditional original files exercise only nonvoting reads. Native promotion
 * remains in the indivisible joining TCP history, not in these fixtures. */
class V53JoiningEndpointTest {
    @TempDir Path temp;
    V53JoiningRetentionNetworkTest.Local local()throws Exception {
        var helper=new V53JoiningRetentionNetworkTest();helper.temp=temp;return helper.new Local();
    }
    MembershipJoiningEndpoint.ReadOnly endpoint(V53JoiningRetentionNetworkTest.Local l,MembershipSourcePull.Guard guard)throws Exception {
        return new MembershipJoiningEndpoint.ReadOnly(l.reader,l.b,bounds(),guard,l.clock::get,0,BUDGET);
    }
    MembershipFormat.Decoded request(V53JoiningRetentionNetworkTest.Local l,String kind,Map<String,Object> payload)throws Exception {
        return MembershipActivation.frame(kind,l.reader.activationContext(),l.source.activationIdentity(),l.reader.activationIdentity(),
                l.source.discoveryState(l.a).ballot(),UUID.randomUUID(),1,payload);
    }
    MembershipSourcePull pull(V53JoiningRetentionNetworkTest.Local l,MembershipJoiningEndpoint.ReadOnly endpoint)throws Exception {
        return MembershipSourcePull.prefix(l.source,new MembershipDiscovery.Hint(l.reader.activationIdentity(),l.reader.activationContext().cut,false),
                l.a,bounds(),(p,q,k,d)->{try{assertEquals(l.reader.activationIdentity(),p);return CompletableFuture.completedFuture(endpoint.handle(l.source.activationIdentity(),q));}
                    catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}},()->{},l.clock::get,0,BUDGET);
    }
    @Test void statusAndCompleteGenerationReadsNeverCreateVotingOrLedgerAuthority()throws Exception {
        try(var l=local()) {
            var before=l.reader.discoveryState(l.b);var files=V53ReplayFilesTest.files(l.path.getParent().resolve("reader"));var usage=l.b.usage();
            try(var endpoint=endpoint(l,()->{});var prefix=pull(l,endpoint);var generation=pull(l,endpoint)) {
                var reply=endpoint.handle(l.source.activationIdentity(),request(l,"STATUS_PROBE",Map.of("nonce",UUID.randomUUID().toString())));
                assertEquals("STATUS",reply.kind());assertEquals(false,object(reply.value().get("payload")).get("ready"));
                var received=prefix.fetchPrefix(temp.resolve("prefix"));assertArrayEquals(l.reader.floorCopyCurrent().capsule.packet.bytes(),received.packet().bytes());
                var complete=generation.fetchGeneration(prefix);assertEquals(l.reader.activationIdentity(),complete.owner);
                assertArrayEquals(l.reader.floorCopyCurrent().fileBytes("generation.gsr"),complete.fileBytes("generation.gsr"));
                assertEquals(before,l.reader.discoveryState(l.b));assertEquals(files,V53ReplayFilesTest.files(l.path.getParent().resolve("reader")));
            }
            assertEquals(usage,l.b.usage());
        }
    }
    @Test void votingRequestsAndArbitraryReferencesRefuseBeforeObservingHigherBallot()throws Exception {
        try(var l=local();var endpoint=endpoint(l,()->{})) {
            var before=l.reader.discoveryState(l.b);var files=V53ReplayFilesTest.files(l.path.getParent().resolve("reader"));
            var prepare=request(l,"PREPARE",Map.of("promise",l.source.promised().orElseThrow().digest()));
            var fields=new TreeMap<>(prepare.value());var ballot=new TreeMap<>(object(fields.get("ballot")));ballot.put("counter",99L);fields.put("ballot",ballot);
            var higher=decode(encode("wire","PREPARE",fields),"wire","PREPARE");
            assertThrows(IllegalArgumentException.class,()->endpoint.handle(l.source.activationIdentity(),higher));
            for(String reference:List.of(l.source.originalSource().basis.digest(),l.reference(),"ff".repeat(32))) {
                var chunk=request(l,"CHUNK",Map.of("action","REQUEST","id",UUID.randomUUID().toString(),"offset",0L,"digest",reference,"bytes",""));
                assertThrows(IllegalArgumentException.class,()->endpoint.handle(l.source.activationIdentity(),chunk));
            }
            assertEquals(before,l.reader.discoveryState(l.b));assertEquals(files,V53ReplayFilesTest.files(l.path.getParent().resolve("reader")));
        }
    }
    @Test void wrongIdentityAndExpiredOrRevokedExistingTraceRefuse()throws Exception {
        for(String fault:List.of("identity","deadline","revoked","closed"))try(var l=local()) {
            var allowed=new AtomicBoolean(true);
            try(var endpoint=endpoint(l,()->{if(!allowed.get())throw new IOException("revoked original preparation");})) {
                var request=request(l,"CHUNK",Map.of("action","REQUEST","id",UUID.randomUUID().toString(),"offset",0L,
                        "digest",MembershipContext.cutDigest(l.reader.activationContext().cut),"bytes",""));
                assertEquals("SOURCE_OFFER",endpoint.handle(l.source.activationIdentity(),request).kind());
                switch(fault){case "deadline"->l.clock.set(BUDGET);case "revoked"->allowed.set(false);case "closed"->endpoint.close();}
                var sender=fault.equals("identity")?V53DeclarationsTest.node(2):l.source.activationIdentity();
                assertThrows(Exception.class,()->endpoint.handle(sender,request));
            }
        }
    }
    @Test void conditionalOwnersCannotPromoteOrResumeAndNeverCreateVotingScratch()throws Exception {
        try(var l=local()) {
            var scratch=temp.resolve("forbidden-voting");var config=storage(temp.resolve("materialization"),1);
            MembershipSourcePull.Link link=(p,q,k,d)->{throw new AssertionError("no I/O before native admission");};
            for(boolean joined:List.of(false,true)) {
                var owner=joined?l.reader:l.source;var pool=joined?l.b:l.a;var usage=pool.usage();
                assertThrows(IllegalArgumentException.class,()->owner.joiningEndpointReady(pool));
                assertThrows(IllegalArgumentException.class,()->new MembershipJoiningEndpoint<>(owner,pool,bounds(),link,scratch,l.clock::get,0,BUDGET,builder().configuration(),config));
                assertThrows(IllegalArgumentException.class,()->MembershipJoiningEndpoint.resume(owner,pool,bounds(),link,scratch,l.clock::get,BUDGET,builder().configuration(),config));
                assertFalse(Files.exists(scratch));assertEquals(usage,pool.usage());
            }
        }
    }
}
