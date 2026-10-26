package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ActivationTest.*;

class V53MembershipWireTest {
    static Decoded sample(String kind)throws Exception {
        return decode(V53FormatTest.bytes(V53FormatTest.sample("wire",kind)),"wire",kind);
    }
    @Test void allFrozenWireKindsKeepTheirExactBytesAndCallerBounds()throws Exception {
        for(String kind:object(CATALOG.get("wire")).keySet()) {
            var original=sample(kind);assertEquals(original.size(),original.bytes().length);
            assertArrayEquals(original.bytes(),MembershipWire.decode(original.bytes(),original.size()).bytes());
            assertThrows(IllegalArgumentException.class,()->MembershipWire.decode(original.bytes(),original.size()-1));
            assertThrows(IllegalArgumentException.class,()->MembershipWire.decode(Arrays.copyOf(original.bytes(),original.size()+1),FRAME));
        }
    }
    @Test void untrustedHeadersRejectBeforeBodyAllocation()throws Exception {
        var original=sample("HELLO");byte[] header=Arrays.copyOf(original.bytes(),HEADER);
        assertEquals(original.size()-HEADER,MembershipWire.bodyLength(header,FRAME));
        for(int offset:List.of(0,4,6,8,10)) {
            byte[] bad=header.clone();bad[offset]^=0x7f;
            assertThrows(IllegalArgumentException.class,()->MembershipWire.bodyLength(bad,FRAME),"offset "+offset);
        }
        for(int size:List.of(0,-1,Integer.MAX_VALUE,FRAME)) {
            byte[] bad=header.clone();ByteBuffer.wrap(bad).putInt(12,size);
            assertThrows(IllegalArgumentException.class,()->MembershipWire.bodyLength(bad,FRAME));
        }
        assertThrows(IllegalArgumentException.class,()->MembershipWire.bodyLength(Arrays.copyOf(header,HEADER-1),FRAME));
        byte[] corrupt=original.bytes();corrupt[HEADER]^=1;
        assertThrows(IllegalArgumentException.class,()->MembershipWire.decode(corrupt,FRAME));
    }
    @Test void fullCorrelationAndPermanentIdentitiesAreRequiredEvenForRejects()throws Exception {
        var request=sample("PREPARE");var reply=response(request,"PROMISE",Map.of("basis","1".repeat(64)));
        MembershipWire.correlated(request,reply,"PROMISE");
        var reject=response(request,"REJECT",Map.of("promised",request.value().get("ballot"),"reason","NOT_READY"));
        MembershipWire.correlated(request,reject,"PROMISE");
        var drift=new TreeMap<String,Object>();drift.put("root","2".repeat(64));drift.put("view","2".repeat(64));
        drift.put("trace",new UUID(99,53).toString());drift.put("sequence",number(reply.value().get("sequence"))+1);
        var ballot=new TreeMap<>(object(reply.value().get("ballot")));ballot.put("counter",number(ballot.get("counter"))+1);drift.put("ballot",ballot);
        for(var entry:drift.entrySet())for(var frame:List.of(reply,reject))
            assertThrows(IllegalArgumentException.class,()->MembershipWire.correlated(request,changed(frame,entry.getKey(),entry.getValue()),"PROMISE"),entry.getKey());
        var sender=new TreeMap<>(object(reply.value().get("sender")));sender.put("storage",new UUID(99,54).toString());
        assertThrows(IllegalArgumentException.class,()->MembershipWire.correlated(request,changed(reply,"sender",sender),"PROMISE"));
        assertThrows(IllegalArgumentException.class,()->MembershipWire.correlated(request,reply,"STATUS"));
        assertThrows(IllegalArgumentException.class,()->MembershipWire.correlated(request,reply,"UNKNOWN"));
    }
    @Test void receiveReservationGrowsAtomicallyAndPreservesSlotOnCapacityFailure() {
        var resources=new MembershipResources(MembershipResources.METADATA_LIMIT,1024,100);
        try(var a=resources.reserve(MembershipResources.Unit.CONTROL,"a",48);
            var b=resources.reserve(MembershipResources.Unit.CONTROL,"b",48)) {
            assertThrows(IllegalArgumentException.class,()->a.reserveControl(53));assertEquals(96,resources.usage().queued());
            a.reserveControl(52);a.reserveControl(52);assertEquals(100,resources.usage().queued());assertEquals(2,resources.usage().leases());
            assertThrows(IllegalArgumentException.class,()->a.reserveControl(51));
            assertThrows(IllegalArgumentException.class,()->a.reserveControl(Long.MAX_VALUE));
            b.close();a.reserveControl(100);assertEquals(100,resources.usage().queued());
            assertThrows(IllegalArgumentException.class,()->b.reserveControl(48));
        }
        assertEquals(0,resources.usage().queued());assertEquals(0,resources.usage().leases());
        try(var other=resources.reserve(MembershipResources.Unit.WAITER,"other",0)) {
            assertThrows(IllegalArgumentException.class,()->other.reserveControl(1));
        }
    }
}
