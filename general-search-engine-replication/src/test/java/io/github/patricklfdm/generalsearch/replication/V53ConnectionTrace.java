package io.github.patricklfdm.generalsearch.replication;

import java.net.InetSocketAddress;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.Decoded;

/** Attempt-scoped observations, never protocol identities or vote authority. */
final class V53ConnectionTrace implements MembershipTransport.Events {
    private final String node;
    private final List<Map<String,Object>> events,wire;
    V53ConnectionTrace(String node,List<Map<String,Object>> events,List<Map<String,Object>> wire) {
        this.node=node;this.events=events;this.wire=wire;
    }
    private static Map<String,Object> address(InetSocketAddress value) {
        return Map.of("address",value.getAddress().getHostAddress(),"port",value.getPort());
    }
    static Map<String,Object> identity(MembershipTransport.Connection connection) {
        return Map.of("id",connection.id().toString(),"local",address(connection.local()),"remote",address(connection.remote()));
    }
    private Map<String,Object> row(String event,Decoded request,MembershipTransport.Connection connection) {
        var row=new TreeMap<String,Object>();row.put("node",node);row.put("scope","connection-test");row.put("event",event);
        row.put("request",request.digest());row.put("kind",request.kind());row.put("connection",identity(connection));return row;
    }
    @Override public void at(String event,Decoded request,Decoded response) {throw new IllegalStateException("connection observation missing");}
    @Override public void at(String event,Decoded request,Decoded response,MembershipTransport.Connection connection) {
        var row=row(event,request,connection);
        if(event.equals("BEFORE_REQUEST_WRITE"))row.put("bytes",Base64.getEncoder().encodeToString(request.bytes()));
        if(response!=null){row.put("response",response.digest());row.put("responseKind",response.kind());}
        synchronized(events) {
            events.add(row);
            if(event.equals("BEFORE_RESPONSE_WRITE")) {
                var answer=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));
                answer.put("withheld",false);answer.put("connection",identity(connection));wire.add(answer);
            }
        }
    }
    @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason,MembershipTransport.Connection connection) {
        var row=row("NETWORK_ATTEMPT_FAILED",request,connection);row.put("direction",outbound?"OUTBOUND":"INBOUND");row.put("reason",reason.name());events.add(row);
    }
}
