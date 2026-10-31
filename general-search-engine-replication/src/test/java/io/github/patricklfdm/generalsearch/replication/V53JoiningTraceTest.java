package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.Decoded;
import static io.github.patricklfdm.generalsearch.replication.V53ActivationTest.response;

class V53JoiningTraceTest {
    @Test void additionalDiagnosticsPreserveBothCallbackMethodsAndOriginalOrder()throws Exception {
        var events=new ArrayList<Map<String,Object>>();var wire=new ArrayList<Map<String,Object>>();
        var observed=new ArrayList<String>();var trace=new V53JoiningTrace("node-4",events,wire);
        var request=V53MembershipWireTest.sample("PREPARE");
        var transport=trace.transport("continuation-endpoint",new MembershipTransport.Events() {
            @Override public void at(String event,Decoded q,Decoded a) {
                assertSame(request,q);assertEquals(event,events.getLast().get("event"));observed.add(event);
            }
            @Override public void failed(boolean outbound,Decoded q,MembershipTransport.Reason reason)throws java.io.IOException {
                assertSame(request,q);assertEquals("NETWORK_ATTEMPT_FAILED",events.getLast().get("event"));
                assertEquals(outbound?"OUTBOUND":"INBOUND",events.getLast().get("direction"));
                observed.add(reason.name());throw new java.io.IOException("diagnostic failure after original capture");
            }
        });
        transport.at("AFTER_REQUEST_READ",request,null);
        var error=assertThrows(java.io.IOException.class,()->transport.failed(false,request,MembershipTransport.Reason.PROTOCOL));
        assertEquals("diagnostic failure after original capture",error.getMessage());
        assertEquals(List.of("AFTER_REQUEST_READ","PROTOCOL"),observed);assertEquals(2,events.size());
        assertEquals("continuation-endpoint",events.getLast().get("scope"));assertTrue(wire.isEmpty());
    }
    @Test void oldRequestObservationsKeepUnansweredAttemptsWithoutInventingResponses()throws Exception {
        var events=new ArrayList<Map<String,Object>>();var request=V53MembershipWireTest.sample("PREPARE");
        for(int attempt=0;attempt<2;attempt++)V53JoiningTrace.requestObservation(events,"node-1","BEFORE_REQUEST_WRITE",request);
        V53JoiningTrace.requestObservation(events,"node-2","AFTER_REQUEST_READ",request);
        V53JoiningTrace.requestObservation(events,"node-2","BEFORE_RESPONSE_WRITE",request);
        V53JoiningTrace.requestObservation(events,"node-1","AFTER_RESPONSE_READ",request);
        assertEquals(List.of("NETWORK_SEND","NETWORK_SEND","NETWORK_REQUEST"),events.stream().map(v->v.get("event")).toList());
        assertEquals(events.get(0),events.get(1));
        assertArrayEquals(request.bytes(),Base64.getDecoder().decode((String)events.getFirst().get("bytes")));
        assertEquals(request.digest(),events.getLast().get("request"));
        assertFalse(events.getLast().containsKey("bytes"));
        assertTrue(events.stream().noneMatch(v->v.containsKey("response")));
    }
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
