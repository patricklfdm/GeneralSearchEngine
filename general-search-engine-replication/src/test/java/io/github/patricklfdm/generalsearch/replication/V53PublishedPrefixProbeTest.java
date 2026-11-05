package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Call-boundary regression only; not original published learner authority. */
class V53PublishedPrefixProbeTest {
    static Decoded request() {
        var source=V53DeclarationsTest.node(1);var peer=V53DeclarationsTest.node(2);
        return decode(encode("wire","CHUNK",Map.of("root","aa".repeat(32),"view","bb".repeat(32),
                "sender",MembershipBootstrapSeed.identity(peer),"recipient",MembershipBootstrapSeed.identity(source),
                "ballot",Map.of("counter",1L,"proposer","node-2","incarnation",peer.storageId().toString()),
                "trace",UUID.randomUUID().toString(),"sequence",1L,
                "payload",Map.of("id",UUID.randomUUID().toString(),"action","REQUEST","offset",0L,"digest","cc".repeat(32),"bytes",""))),"wire","CHUNK");
    }
    static class Fixture {
        final MembershipResources pool=V53SessionExportOwnershipTest.budget();
        final List<Map<String,Object>> events=new ArrayList<>();
        final List<Long> points=new ArrayList<>();
        final AtomicInteger opened=new AtomicInteger(),referenced=new AtomicInteger(),closed=new AtomicInteger();
        final List<Map<String,Object>> observed=new ArrayList<>() {
            @Override public boolean add(Map<String,Object> row) {
                events.add(row);points.add(pool.observationCheckpoint().sequence());return super.add(row);
            }
        };
        IOException openingFailure,referenceFailure;RuntimeException closingFailure;boolean empty;
        MembershipTransferExport open()throws IOException {
            opened.incrementAndGet();if(openingFailure!=null)throw openingFailure;
            var lease=pool.reserve(MembershipResources.Unit.CONTROL,V53ProbeExportOwnershipTest.name("prefix-export"),4096);
            return new MembershipTransferExport() {
                public MembershipContext context(){throw new AssertionError("probe does not inspect context");}
                public MembershipIdentity identity(){throw new AssertionError("probe does not inspect identity");}
                public Map<String,Object> ballot(){throw new AssertionError("probe does not inspect ballot");}
                public List<MembershipResources.Lease> closeReservations(){return List.of(lease);}
                public Map<String,MembershipSourceExport.Content> references()throws IOException {
                    referenced.incrementAndGet();if(referenceFailure!=null)throw referenceFailure;
                    if(empty)return Map.of();
                    return Map.of("b".repeat(64),new MembershipSourceExport.Content("c".repeat(64),17,MembershipTransfer.Kind.CAPSULE),
                                  "a".repeat(64),new MembershipSourceExport.Content("a".repeat(64),29,MembershipTransfer.Kind.APPLICATION));
                }
                public byte[] read(String digest,long offset,int maximum){throw new AssertionError("probe never reads body bytes");}
                public void close(){closed.incrementAndGet();lease.close();if(closingFailure!=null)throw closingFailure;}
            };
        }
        void run(boolean enabled)throws IOException {V53PublishedPrefixProbe.run(enabled,observed,"node-1",request(),pool,this::open);}
        List<String> names(){return events.stream().map(v->(String)v.get("event")).toList();}
    }
    @Test void oneOriginalCallBindsBeforeLiveReferenceAndAfterCleanupWithoutReadingBodies()throws Exception {
        var f=new Fixture();var q=request();V53PublishedPrefixProbe.run(true,f.observed,"node-1",q,f.pool,f::open);
        assertEquals(List.of("PUBLISHED_PREFIX_PROBE_BEGIN","PUBLISHED_PREFIX_PROBE_REFERENCES","PUBLISHED_PREFIX_PROBE_RETURNED"),f.names());
        assertEquals(1,f.opened.get());assertEquals(1,f.referenced.get());assertEquals(1,f.closed.get());
        assertTrue(f.points.get(0)<f.points.get(1));assertTrue(f.points.get(1)<f.points.get(2));
        assertEquals(q.digest(),f.events.getFirst().get("request"));
        assertArrayEquals(q.bytes(),Base64.getDecoder().decode((String)f.events.getFirst().get("bytes")));
        var contents=list(f.events.get(1).get("contents"));assertEquals(2,contents.size());
        assertEquals("a".repeat(64),object(contents.getFirst()).get("reference"));
        assertEquals(Map.of("reference","b".repeat(64),"digest","c".repeat(64),"bytes",17L,"kind","CAPSULE"),contents.get(1));
        assertEquals(0,f.pool.usage().leases());assertFalse(f.pool.controlCloseObservations().failed());
    }
    @Test void disabledMarkersStillPerformTheOriginalCallAndCleanup()throws Exception {
        var f=new Fixture();f.run(false);assertTrue(f.events.isEmpty());assertEquals(1,f.opened.get());
        assertEquals(1,f.referenced.get());assertEquals(1,f.closed.get());assertEquals(0,f.pool.usage().leases());
    }
    @Test void factoryFailureNeverInventsReferencesCleanupOrReturn() {
        var f=new Fixture();f.openingFailure=new IOException("factory");assertSame(f.openingFailure,assertThrows(IOException.class,()->f.run(true)));
        assertEquals(1,f.events.size());assertEquals(0,f.referenced.get());assertEquals(0,f.closed.get());
    }
    @Test void referenceFailureKeepsOriginalExceptionAndClosesWithoutSuccessMarkers() {
        var f=new Fixture();f.referenceFailure=new IOException("references");assertSame(f.referenceFailure,assertThrows(IOException.class,()->f.run(true)));
        assertEquals(1,f.events.size());assertEquals(1,f.closed.get());assertEquals(0,f.pool.usage().leases());
    }
    @Test void failedCleanupCannotBecomeASuccessfulReturnEvenAtZeroUsage() {
        var f=new Fixture();f.closingFailure=new IllegalStateException("cleanup");assertSame(f.closingFailure,assertThrows(IllegalStateException.class,()->f.run(true)));
        assertEquals(2,f.events.size());assertEquals(1,f.closed.get());assertEquals(0,f.pool.usage().leases());
    }
    @Test void originalPrimaryAndSuppressedExceptionsArePreserved() {
        var f=new Fixture();f.referenceFailure=new IOException("references");f.closingFailure=new IllegalStateException("cleanup");
        var actual=assertThrows(IOException.class,()->f.run(true));assertSame(f.referenceFailure,actual);
        assertArrayEquals(new Throwable[]{f.closingFailure},actual.getSuppressed());assertEquals(1,f.events.size());assertEquals(1,f.closed.get());
    }
    @Test void originalNonemptyAssertionStillClosesWithoutInventedSuccess() {
        var f=new Fixture();f.empty=true;assertThrows(AssertionError.class,()->f.run(true));
        assertEquals(1,f.events.size());assertEquals(1,f.closed.get());assertEquals(0,f.pool.usage().leases());
    }
}
