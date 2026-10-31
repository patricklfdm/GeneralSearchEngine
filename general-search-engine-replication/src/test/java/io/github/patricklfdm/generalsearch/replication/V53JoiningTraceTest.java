package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53ActivationTest.response;

class V53JoiningTraceTest {
    @Test void callbacksKeepActualForceAndResponseOrderAcrossOwners()throws Exception {
        var events=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var wire=Collections.synchronizedList(new ArrayList<Map<String,Object>>());
        var trace=new V53JoiningTrace("node-4",events,wire);
        var request=V53MembershipWireTest.sample("PREPARE");
        var reply=response(request,"PROMISE",Map.of("basis","1".repeat(64)));
        var cut=trace.cut("continuation-owner");var transport=trace.transport("continuation-endpoint");
        assertTrue(events.isEmpty(),"registering a callback does not prove an owner opened");
        var forced=new CountDownLatch(1);
        try(var executor=Executors.newVirtualThreadPerTaskExecutor()) {
            var observed=executor.submit(()->{
                assertTrue(forced.await(5,TimeUnit.SECONDS));
                transport.at("BEFORE_RESPONSE_WRITE",request,reply);return null;
            });
            cut.at("BASIS_FORCED");events.add(Map.of("node","node-1","event","OLD_OWNER_OBSERVATION"));forced.countDown();
            observed.get(5,TimeUnit.SECONDS);
        }
        assertEquals(List.of("BASIS_FORCED","OLD_OWNER_OBSERVATION","BEFORE_RESPONSE_WRITE"),events.stream().map(v->v.get("event")).toList());
        assertEquals("continuation-owner",events.getFirst().get("scope"));
        assertEquals(reply.digest(),events.getLast().get("response"));
        var exchange=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,reply));exchange.put("withheld",false);
        assertEquals(List.of(exchange),wire);
    }
    @Test void attemptedRequestsAndReadResponsesDoNotInventWireSuccessOrDuplicateIt()throws Exception {
        var events=new ArrayList<Map<String,Object>>();var wire=new ArrayList<Map<String,Object>>();
        var trace=new V53JoiningTrace("node-4",events,wire);
        var request=V53MembershipWireTest.sample("PREPARE");
        var reply=response(request,"PROMISE",Map.of("basis","1".repeat(64)));
        trace.transport("initial-endpoint").at("BEFORE_REQUEST_WRITE",request,null);
        assertArrayEquals(request.bytes(),Base64.getDecoder().decode((String)events.getFirst().get("bytes")));
        assertFalse(events.getFirst().containsKey("response"));assertTrue(wire.isEmpty());
        trace.transport("initial-endpoint").at("AFTER_RESPONSE_READ",request,reply);
        assertEquals(reply.digest(),events.getLast().get("response"));assertTrue(wire.isEmpty());
        trace.cut("retaining-owner").at("BASIS_FORCED");trace.cut("stable-cold-owner").at("BASIS_FORCED");
        assertEquals(List.of("retaining-owner","stable-cold-owner"),events.subList(2,4).stream().map(v->v.get("scope")).toList());
    }
}
