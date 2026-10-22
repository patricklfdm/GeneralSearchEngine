package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipResources.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class V53ResourceTransferTest {
    static MembershipTransfer.Binding binding(byte[] bytes) {
        return new MembershipTransfer.Binding("01".repeat(32),new UUID(1,1),new UUID(2,2),V53DeclarationsTest.node(1),
                new UUID(3,3),"02".repeat(32),"03".repeat(32),MembershipFormat.hash(bytes),bytes.length,MembershipTransfer.Kind.RECORD);
    }
    @Test void completeMetadataEnvelopeIncludesEveryCopyAndCompletionHeadroom() {
        var budget=new MembershipResources(1024*MIB);var leases=new ArrayList<MembershipResources.Lease>();
        for(Unit unit:List.of(Unit.GENERATION,Unit.SOURCE,Unit.LEARNER,Unit.JOURNAL,Unit.CATALOG,Unit.MISC))
            for(int i=0;i<unit.count;i++)leases.add(budget.reserve(unit,unit.name()+i,unit.bytes));
        assertEquals(324*MIB,budget.usage().metadata());assertEquals(224*MIB,budget.usage().staging());
        assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.SOURCE,"another-campaign",1));
        assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.GENERATION,"third",1));
        leases.forEach(MembershipResources.Lease::close);leases.forEach(MembershipResources.Lease::close);
        assertEquals(0,budget.usage().leases());assertEquals(0,budget.usage().metadata());assertEquals(0,budget.usage().staging());
        var small=new MembershipResources(HEADROOM+4*MIB,64*MIB,64*MIB);
        try(var ordinary=small.reserve(Unit.SOURCE,"source",4*MIB)) {
            assertThrows(IllegalArgumentException.class,()->small.reserve(Unit.SOURCE,"crowd-out-final",1));
            try(var journal=small.reserve(Unit.JOURNAL,"rotation",32*MIB);var catalog=small.reserve(Unit.CATALOG,"catalog",2*MIB);
                var misc=small.reserve(Unit.MISC,"final-promise-selector",2*MIB)) { assertEquals(40*MIB,small.usage().metadata()); }
        }
    }
    @Test void stagingCountsMetadataAndApplicationTogetherAndQueueIsGlobal() {
        var budget=new MembershipResources(384*MIB,40,10);
        try(var source=budget.reserve(Unit.SOURCE,"source",20);var app=budget.reserve(Unit.APPLICATION,"app",20)) {
            assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.APPLICATION,"other-app",1));
            assertEquals(40,budget.usage().staging());
            try(var a=budget.reserve(Unit.CONTROL,"peer-a",6);var b=budget.reserve(Unit.CONTROL,"peer-b",4)) {
                assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.CONTROL,"peer-c",1));
                assertEquals(10,budget.usage().queued());
            }
        }
        var waiters=new ArrayList<MembershipResources.Lease>();
        for(int i=0;i<64;i++)waiters.add(budget.reserve(Unit.WAITER,"w"+i,0));
        assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.WAITER,"65",0));waiters.forEach(MembershipResources.Lease::close);
        assertThrows(IllegalArgumentException.class,()->budget.reserve(Unit.SOURCE,"overflow",Long.MAX_VALUE));
        assertEquals(0,budget.usage().leases());
    }
    @Test void lifetimeExhaustionBlocksNewMembershipButNotOrdinaryReservations() {
        var budget=new MembershipResources(64*MIB);
        assertDoesNotThrow(()->budget.admitChange(255,511,63,1));
        for(long[] values:new long[][]{{256,3,0,0},{0,512,0,1},{0,3,64,0},{-1,3,0,0}})
            assertThrows(IllegalArgumentException.class,()->budget.admitChange(values[0],values[1],values[2],(int)values[3]));
        try(var data=budget.reserve(Unit.CONTROL,"stable-data",128)) { assertEquals(128,budget.usage().queued()); }
    }
    @Test void transferIsBoundBeforeAnyWriteAndDuplicateAcknowledgementDoesNotDuplicateBytes() throws Exception {
        byte[] original="abcdef".getBytes(java.nio.charset.StandardCharsets.US_ASCII);var expected=binding(original);
        var sink=new ByteArrayOutputStream();var budget=new MembershipResources(64*MIB);var validations=new AtomicInteger();
        try(var transfer=new MembershipTransfer(expected,budget,Unit.SOURCE,sink,3)) {
            byte[] first=Arrays.copyOf(original,3),second=Arrays.copyOfRange(original,3,6);
            var wrong=new MembershipTransfer.Binding(expected.root(),new UUID(9,9),expected.transfer(),expected.source(),expected.basisId(),
                    expected.basisDigest(),expected.cutDigest(),expected.digest(),expected.bytes(),expected.kind());
            assertThrows(IllegalArgumentException.class,()->transfer.chunk(wrong,0,first,MembershipFormat.hash(first)));
            assertThrows(IllegalArgumentException.class,()->transfer.chunk(expected,3,second,MembershipFormat.hash(second)));
            assertThrows(IllegalArgumentException.class,()->transfer.chunk(expected,0,first,"00".repeat(32)));
            assertEquals(0,sink.size());
            transfer.chunk(expected,0,first,MembershipFormat.hash(first));transfer.chunk(expected,0,first,MembershipFormat.hash(first));
            assertEquals(3,sink.size());assertEquals(3,transfer.received());
            assertThrows(IllegalArgumentException.class,()->transfer.finish(expected,validations::incrementAndGet));
            transfer.chunk(expected,3,second,MembershipFormat.hash(second));transfer.finish(expected,validations::incrementAndGet);
            transfer.finish(expected,validations::incrementAndGet);
            assertEquals(1,validations.get());assertEquals(MembershipTransfer.State.VERIFIED,transfer.state());assertArrayEquals(original,sink.toByteArray());
            assertEquals(6,budget.usage().staging());
        }
        assertEquals(0,budget.usage().staging());
    }
    @Test void completeDigestSemanticOrSinkFailureNeverBecomesVerifiedOrSilentlyReleasesOwnedBytes() throws Exception {
        byte[] body={1,2,3};var expected=binding(body);var budget=new MembershipResources(64*MIB);
        for(boolean failSink:new boolean[]{false,true}) {
            OutputStream sink=failSink?new OutputStream(){public void write(int value)throws IOException{throw new IOException("disk full");}}:new ByteArrayOutputStream();
            try(var transfer=new MembershipTransfer(expected,budget,Unit.SOURCE,sink,8)) {
                if(failSink)assertThrows(IOException.class,()->transfer.chunk(expected,0,body,MembershipFormat.hash(body)));
                else {
                    transfer.chunk(expected,0,body,MembershipFormat.hash(body));
                    assertThrows(IllegalArgumentException.class,()->transfer.finish(expected,()->{throw new IllegalArgumentException("foreign catalog");}));
                }
                assertEquals(MembershipTransfer.State.FAILED,transfer.state());assertEquals(3,budget.usage().staging());
                assertThrows(IllegalArgumentException.class,()->transfer.finish(expected,()->fail("must not retry semantic failure")));
            }
        }
        var wrong=new MembershipTransfer.Binding(expected.root(),expected.session(),expected.transfer(),expected.source(),expected.basisId(),
                expected.basisDigest(),expected.cutDigest(),"00".repeat(32),3,expected.kind());
        try(var transfer=new MembershipTransfer(wrong,budget,Unit.SOURCE,new ByteArrayOutputStream(),8)) {
            transfer.chunk(wrong,0,body,MembershipFormat.hash(body));assertThrows(IllegalArgumentException.class,()->transfer.finish(wrong,()->fail("hash before semantic check")));
            assertEquals(MembershipTransfer.State.FAILED,transfer.state());
        }
    }
    @Test void changedOriginalBasisCutSourceAndCapacityRejectBeforeSinkUse() {
        var expected=binding(new byte[]{1});var budget=new MembershipResources(384*MIB,1,64*MIB);
        try(var used=budget.reserve(Unit.APPLICATION,"occupied",1)) {
            assertThrows(IllegalArgumentException.class,()->new MembershipTransfer(expected,budget,Unit.SOURCE,new OutputStream(){public void write(int v){fail("preallocation rejection");}},1));
            assertEquals(1,budget.usage().leases());
        }
        for(int change=0;change<3;change++) {
            var altered=new MembershipTransfer.Binding(expected.root(),expected.session(),expected.transfer(),change==0?V53DeclarationsTest.node(2):expected.source(),
                    expected.basisId(),change==1?"09".repeat(32):expected.basisDigest(),change==2?"09".repeat(32):expected.cutDigest(),expected.digest(),1,expected.kind());
            var sink=new ByteArrayOutputStream();
            try(var transfer=new MembershipTransfer(expected,budget,Unit.SOURCE,sink,1)) {
                assertThrows(IllegalArgumentException.class,()->transfer.chunk(altered,0,new byte[]{1},MembershipFormat.hash(new byte[]{1})));assertEquals(0,sink.size());
            }
        }
    }
    @Test void retryKeepsOriginalBytesDeadlineAndThreeTotalAttempts() {
        var exchange=new MembershipExchange("01".repeat(32),100,50);
        assertThrows(IllegalArgumentException.class,()->exchange.attempt("02".repeat(32),101));assertEquals(0,exchange.attempts());
        for(long now:new long[]{100,120,149})exchange.attempt("01".repeat(32),now);
        assertThrows(IllegalArgumentException.class,()->exchange.attempt("01".repeat(32),149));
        var late=new MembershipExchange("01".repeat(32),100,50);late.attempt("01".repeat(32),101);
        assertThrows(IllegalArgumentException.class,()->late.attempt("01".repeat(32),150));assertEquals(1,late.attempts());
        assertThrows(IllegalArgumentException.class,()->late.complete("01".repeat(32),150));
        late.complete("01".repeat(32),149);assertThrows(IllegalArgumentException.class,()->late.attempt("01".repeat(32),110));
        var wrapped=new MembershipExchange("01".repeat(32),Long.MAX_VALUE-5,20);wrapped.attempt("01".repeat(32),Long.MIN_VALUE+3);
        assertEquals(1,wrapped.attempts());
    }
}
