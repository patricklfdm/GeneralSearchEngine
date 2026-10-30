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

/** Actual old grants and read-only joining handlers. Synthetic completion bytes
 * test only client parsing/retries, never native initialization authority. */
class V53JoiningCompletionTest {
    @TempDir Path temp;
    V53JoiningRetentionNetworkTest.Local local()throws Exception {
        var helper=new V53JoiningRetentionNetworkTest();helper.temp=temp;return helper.new Local();
    }
    MembershipJoiningCompletion.Probe probe(V53JoiningRetentionNetworkTest.Local l,MembershipSourcePull.Link link,MembershipSourcePull.Guard guard)throws Exception {
        return new MembershipJoiningCompletion.Probe(l.source,l.a,bounds(),link,guard,l.clock::get,0,BUDGET,V53JoiningPreparationTest.hint(l));
    }
    static Decoded reply(Decoded request,String kind,Object payload) {
        var fields=new TreeMap<>(request.value());fields.put("sender",request.value().get("recipient"));fields.put("recipient",request.value().get("sender"));
        fields.put("payload",payload);return decode(encode("wire",kind,fields),"wire",kind);
    }
    static Decoded data(Decoded request,String kind,byte[] bytes) {
        var p=object(request.value().get("payload"));Object payload=switch(kind) {
            case "SOURCE_OFFER"->Map.of("id",p.get("id"),"digest",hash(bytes),"kind","RECORD","bytes",(long)bytes.length);
            case "CHUNK"->Map.of("id",p.get("id"),"action","DATA","offset",p.get("offset"),"digest",hash(bytes),"bytes",Base64.getEncoder().encodeToString(bytes));
            case "TRANSFER_COMMIT"->p;
            default->throw new AssertionError(kind);
        };
        return reply(request,kind,payload);
    }
    static Decoded reject(Decoded request,String reason) {
        return reply(request,"REJECT",Map.of("reason",reason,"promised",request.value().get("ballot")));
    }
    @Test void completionHintUsesBoundedIdenticalReadsWithoutGrantOrPublication()throws Exception {
        for(String drop:List.of("none","SOURCE_OFFER","CHUNK","TRANSFER_COMMIT"))try(var l=local()) {
            var state=l.source.discoveryState(l.a);var files=V53ReplayFilesTest.files(l.path);var usage=l.a.usage();
            byte[] bytes=MembershipJoiningCompletion.bytes(state.context(),l.reader.activationIdentity());
            var dropped=new AtomicBoolean();var sent=new ArrayList<Decoded>();
            try(var probe=probe(l,(p,q,k,d)->{
                assertEquals(l.reader.activationIdentity(),p);assertEquals(BUDGET,d);sent.add(q);
                if(k.equals(drop) && dropped.compareAndSet(false,true))return CompletableFuture.failedFuture(lost());
                return CompletableFuture.completedFuture(data(q,k,bytes));
            },()->{})) {
                assertTrue(probe.run());assertThrows(IllegalArgumentException.class,probe::run);
                assertEquals(drop.equals("none")?0:1,sent.size()-sent.stream().map(Decoded::digest).distinct().count());
                assertTrue(sent.stream().allMatch(q->Set.of("CHUNK","TRANSFER_COMMIT").contains(q.kind())));
            }
            assertEquals(state,l.source.discoveryState(l.a));assertEquals(files,V53ReplayFilesTest.files(l.path));assertEquals(usage,l.a.usage());
            assertTrue(l.source.originalSelection().isEmpty());assertThrows(IllegalArgumentException.class,()->l.reader.joiningEndpointReady(l.b));
        }
    }
    @Test void originalReadOnlyEndpointReportsAbsenceWithoutVotingOrTransfers()throws Exception {
        try(var l=local();var endpoint=new MembershipJoiningEndpoint.ReadOnly(l.reader,l.b,bounds(),()->{},l.clock::get,0,BUDGET)) {
            var before=l.reader.discoveryState(l.b);var usage=l.b.usage();var sent=new ArrayList<Decoded>();
            try(var probe=probe(l,(p,q,k,d)->{
                sent.add(q);try{return CompletableFuture.completedFuture(endpoint.handle(l.source.activationIdentity(),q));}
                catch(IOException|RuntimeException error){return CompletableFuture.failedFuture(error);}
            },()->{})) {assertFalse(probe.run());}
            assertEquals(1,sent.size());assertEquals(before,l.reader.discoveryState(l.b));assertEquals(usage,l.b.usage());
            assertThrows(IllegalArgumentException.class,()->new MembershipJoiningCompletion(l.reader,l.source.activationIdentity(),sent.getFirst(),l.b,l.clock::get,0,BUDGET));
            for(String fault:List.of("offset","view","sender","root","sequence")) {
                var fields=new TreeMap<>(sent.getFirst().value());
                switch(fault){case "offset"->{var payload=new TreeMap<>(object(fields.get("payload")));payload.put("offset",1L);fields.put("payload",payload);}
                    case "view","root"->fields.put(fault,"ff".repeat(32));case "sender"->fields.put("sender",MembershipBootstrapSeed.identity(l.reader.activationIdentity()));
                    case "sequence"->fields.put("sequence",2L);}
                var changed=decode(encode("wire","CHUNK",fields),"wire","CHUNK");
                assertThrows(IllegalArgumentException.class,()->endpoint.handle(l.source.activationIdentity(),changed),fault);
            }
            assertEquals(before,l.reader.discoveryState(l.b));assertEquals(usage,l.b.usage());
        }
    }
    @Test void completeButForeignOrNoncanonicalObservationIsNeverAccepted()throws Exception {
        try(var l=local()) {
            var context=l.source.activationContext();byte[] original=MembershipJoiningCompletion.bytes(context,l.reader.activationIdentity());
            for(String fault:List.of("root","cut","joining","schema","extra","whitespace")) {
                var value=new TreeMap<>(object(parse(original,MembershipJoiningCompletion.MAXIMUM)));
                switch(fault){case "root","schema"->value.put(fault,"ff".repeat(32));case "cut"->value.put("cut",Map.of());
                    case "joining"->value.put("joining",MembershipBootstrapSeed.identity(l.source.activationIdentity()));case "extra"->value.put("ready",true);}
                byte[] bytes=fault.equals("whitespace")?Arrays.copyOf(original,original.length+1):canonical(value,MembershipJoiningCompletion.MAXIMUM);
                try(var probe=probe(l,(p,q,k,d)->CompletableFuture.completedFuture(data(q,k,bytes)),()->{})) {
                    assertThrows(IllegalArgumentException.class,probe::run,fault);
                }
            }
        }
    }
    @Test void refusalAfterOfferOrOtherFailureNeverBecomesNotInitializedOrSuccess()throws Exception {
        for(String fault:List.of("CAPACITY_EXCEEDED","INTEGRITY_FAILURE","STALE_EPOCH","foreign","mid-data","mid-commit","io"))try(var l=local()) {
            byte[] bytes=MembershipJoiningCompletion.bytes(l.source.activationContext(),l.reader.activationIdentity());var requests=new ArrayList<Decoded>();
            try(var probe=probe(l,(p,q,k,d)->{
                requests.add(q);if(fault.equals("io"))return CompletableFuture.failedFuture(new IOException("unclassified I/O"));
                if(fault.startsWith("mid-") && !k.equals(fault.equals("mid-data")?"CHUNK":"TRANSFER_COMMIT"))return CompletableFuture.completedFuture(data(q,k,bytes));
                var rejection=reject(q,fault.startsWith("mid-") || fault.equals("foreign")?"NOT_READY":fault);
                if(fault.equals("foreign")){var changed=new TreeMap<>(rejection.value());changed.put("trace",UUID.randomUUID().toString());rejection=decode(encode("wire","REJECT",changed),"wire","REJECT");}
                return CompletableFuture.completedFuture(rejection);
            },()->{})) {assertThrows(Exception.class,probe::run,fault);}
            assertEquals(fault.equals("mid-data")?2:fault.equals("mid-commit")?3:1,requests.size());
        }
    }
    @Test void completionReadDoesNotRenewDeadlineOrSurviveHigherLocalFence()throws Exception {
        for(String fault:List.of("deadline","fence","guard"))try(var l=local()) {
            var allowed=new AtomicBoolean(true);byte[] bytes=MembershipJoiningCompletion.bytes(l.source.activationContext(),l.reader.activationIdentity());
            try(var probe=probe(l,(p,q,k,d)->{
                if(fault.equals("deadline"))l.clock.set(BUDGET);
                else if(fault.equals("fence"))l.source.observeCurrent(l.in.fixture().source.ballot(21));else allowed.set(false);
                return CompletableFuture.completedFuture(data(q,k,bytes));
            },()->{if(!allowed.get())throw new IOException("preparation revoked");})) {assertThrows(Exception.class,probe::run,fault);}
        }
    }
    @Test void closeCancelsPendingProbeAndDrainsItsResourceOwner()throws Exception {
        try(var l=local()) {
            var usage=l.a.usage();var waiting=new CountDownLatch(1);var pending=new CompletableFuture<Decoded>();
            try(var probe=probe(l,(p,q,k,d)->{waiting.countDown();return pending;},()->{});var threads=Executors.newVirtualThreadPerTaskExecutor()) {
                var call=threads.submit(probe::run);assertTrue(waiting.await(5,TimeUnit.SECONDS));probe.close();
                assertTrue(pending.isCancelled());assertThrows(ExecutionException.class,()->call.get(5,TimeUnit.SECONDS));assertEquals(usage,l.a.usage());
            }
        }
    }
}
