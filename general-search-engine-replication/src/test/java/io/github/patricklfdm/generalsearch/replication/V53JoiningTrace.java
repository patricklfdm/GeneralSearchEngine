package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.nio.file.Path;
import java.util.function.BooleanSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Observations only: share the old owners' event order, without issuing capabilities.
 * A scope identifies the callback registration, not proof that an owner opened. */
final class V53JoiningTrace {
    private final String node;
    private final List<Map<String,Object>> events,wire;
    private V53GrantCapture grants;
    private V53SourceRetirementCapture retirements;
    private Path retirementReplica;
    private Path replica;
    private V53PublicationResourceCapture publicationResources;
    private Path resourceReplica;
    private MembershipResources resources;
    V53JoiningTrace(String node,List<Map<String,Object>> events,List<Map<String,Object>> wire) {
        this.node=Objects.requireNonNull(node);this.events=Objects.requireNonNull(events);this.wire=Objects.requireNonNull(wire);
    }
    void retainGrants(V53GrantCapture grants,Path replica) {
        if(this.grants!=null)throw new IllegalStateException("joining grant observation already bound");
        this.grants=Objects.requireNonNull(grants);this.replica=Objects.requireNonNull(replica);
    }
    void retainRetirements(V53SourceRetirementCapture retirements,Path replica) {
        if(this.retirements!=null)throw new IllegalStateException("joining retirement observation already bound");
        this.retirements=Objects.requireNonNull(retirements);this.retirementReplica=Objects.requireNonNull(replica);
    }
    void retainPublicationResources(V53PublicationResourceCapture capture,Path replica,MembershipResources resources) {
        if(capture==null)return;
        if(publicationResources!=null)throw new IllegalStateException("publication resource observation already bound");
        publicationResources=capture;resourceReplica=Objects.requireNonNull(replica);this.resources=Objects.requireNonNull(resources);
    }
    MembershipBallotAllocator.Cut cut(String scope) {
        Objects.requireNonNull(scope);
        return event->{int index;synchronized(events){index=events.size();events.add(Map.of("node",node,"scope",scope,"event",event));}
            if(grants!=null)grants.at(node,scope,replica,event);
            if(retirements!=null)retirements.at(node,scope,retirementReplica,event);
            if(publicationResources!=null)publicationResources.at(node,scope,resourceReplica,resources,event,index);};
    }
    /** Optional old-owner request observations. Keep their existing response
     * callbacks untouched; an attempted write is not proof of delivery. */
    static void requestObservation(List<Map<String,Object>> events,String node,String event,Decoded request) {
        if(event.equals("BEFORE_REQUEST_WRITE"))events.add(Map.of("node",node,"event","NETWORK_SEND",
                "request",request.digest(),"kind",request.kind(),"bytes",Base64.getEncoder().encodeToString(request.bytes())));
        else if(event.equals("AFTER_REQUEST_READ"))events.add(Map.of("node",node,"event","NETWORK_REQUEST",
                "request",request.digest(),"kind",request.kind()));
    }
    static MembershipTransport.Events withFailures(String node,String scope,List<Map<String,Object>> events,
            BooleanSupplier enabled,MembershipTransport.Events delegate) {
        return new MembershipTransport.Events() {
            @Override public void at(String event,Decoded request,Decoded response)throws java.io.IOException {
                delegate.at(event,request,response);
            }
            @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason) {
                if(!enabled.getAsBoolean())return;
                var row=new TreeMap<String,Object>();row.put("node",node);if(scope!=null)row.put("scope",scope);
                row.put("event","NETWORK_ATTEMPT_FAILED");row.put("direction",outbound?"OUTBOUND":"INBOUND");
                row.put("request",request.digest());row.put("kind",request.kind());row.put("reason",reason.name());events.add(row);
            }
        };
    }
    /** Preserve both callback methods when a fixture adds diagnostics. */
    MembershipTransport.Events transport(String scope,MembershipTransport.Events observer) {
        var collected=transport(scope);Objects.requireNonNull(observer);
        return new MembershipTransport.Events() {
            @Override public void at(String event,Decoded request,Decoded response)throws java.io.IOException {
                collected.at(event,request,response);observer.at(event,request,response);
            }
            @Override public void failed(boolean outbound,Decoded request,MembershipTransport.Reason reason)throws java.io.IOException {
                collected.failed(outbound,request,reason);observer.failed(outbound,request,reason);
            }
        };
    }
    MembershipTransport.Events transport(String scope) {
        Objects.requireNonNull(scope);
        return withFailures(node,scope,events,()->true,(event,request,response)->{
            var row=new TreeMap<String,Object>();row.put("node",node);row.put("scope",scope);row.put("event",event);
            row.put("request",request.digest());row.put("kind",request.kind());
            // Preserve attempted writes too, including requests whose reply is lost.
            if(event.equals("BEFORE_REQUEST_WRITE"))row.put("bytes",Base64.getEncoder().encodeToString(request.bytes()));
            if(response!=null){row.put("response",response.digest());row.put("responseKind",response.kind());}
            events.add(row);
            // The receiver records each response once. AFTER_RESPONSE_READ is
            // an observation in the same sequence, not a second wire exchange.
            if(event.equals("BEFORE_RESPONSE_WRITE")) {
                var exchange=new TreeMap<String,Object>(V53SelectedPullTest.wire(request,response));
                exchange.put("withheld",false);wire.add(exchange);
            }
        });
    }
}
