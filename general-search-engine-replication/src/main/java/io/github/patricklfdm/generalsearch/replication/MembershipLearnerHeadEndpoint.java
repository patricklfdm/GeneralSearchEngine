package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Read-only listener on a real forced learner head. Uses the transport's
 * trusted-private-network identity boundary; it is neither TLS authentication
 * nor voter enrollment. No voting or transfer handler is installed here. */
final class MembershipLearnerHeadEndpoint implements AutoCloseable {
    private final MembershipLearnerHeadObservation observation;
    private final String root;
    private final Map<String,MembershipIdentity> voters;
    private final MembershipTransport transport;
    private final Object guard=new Object();
    private volatile boolean closed,released;

    MembershipLearnerHeadEndpoint(MembershipLearnerHead head,ReplicationBounds bounds,
            MembershipTransport.Events events)throws IOException {
        this(MembershipLearnerHeadObservation.capture(head),bounds,events);
    }
    MembershipLearnerHeadEndpoint(MembershipLearnerDisposition.RetainedSource retained,ReplicationBounds bounds,
            MembershipTransport.Events events)throws IOException {
        this(MembershipLearnerHeadObservation.capture(retained),bounds,events);
    }
    private MembershipLearnerHeadEndpoint(MembershipLearnerHeadObservation observation,ReplicationBounds bounds,
            MembershipTransport.Events events)throws IOException {
        this.observation=observation;
        try {
            Objects.requireNonNull(events);Objects.requireNonNull(bounds);observation.check();
            var source=observation.source();root=source.context.root;
            // Retain only the at-most-five original voter identities, not a
            // second full decoded operation catalog or source packet.
            var originalVoters=new TreeMap<String,MembershipIdentity>();
            for(String node:source.context.voters())originalVoters.put(node,source.context.identities.get(node));
            voters=Map.copyOf(originalVoters);
            transport=new MembershipTransport(source,observation.learner,bounds,observation.resources(),this::answer,(event,request,response)->{
                events.at(event,request,response);
                // External hooks never execute under the lifecycle monitor.
                // Recheck after hooks, immediately before writing any ACK.
                if(event.equals("BEFORE_RESPONSE_WRITE"))synchronized(guard){check();}
            });
        }catch(IOException|RuntimeException|Error error){observation.close();throw error;}
    }
    private void check()throws IOException {require(!closed,"learner head endpoint closed");observation.check();}
    Decoded answer(MembershipIdentity sender,Decoded request)throws IOException {
        synchronized(guard) {
            check();var value=request.value();
            MembershipWire.envelope(request,root,sender,observation.learner);
            require(request.kind().equals("LEARNER_HEAD_QUERY")
                    && sender.equals(voters.get(sender.nodeId().value()))
                    && value.get("view").equals(observation.request.get("expected"))
                    && value.get("ballot").equals(MembershipLearnerDiscovery.correlation(observation.learner))
                    && number(value.get("sequence"))==1
                    && object(value.get("payload")).get("request").equals(observation.request),"learner head query original binding");
            var reply=new TreeMap<>(value);reply.put("sender",value.get("recipient"));reply.put("recipient",value.get("sender"));
            reply.put("payload",Map.of("request",hash(canonical(observation.request,8192)),
                    "endpoint",MembershipRetentionIntent.anchor(observation.endpoint)));
            var answer=decode(encode("wire","LEARNER_HEAD_ACK",reply),"wire","LEARNER_HEAD_ACK");check();return answer;
        }
    }
    boolean closed(){return released;}
    @Override public void close()throws IOException {
        synchronized(guard){closed=true;}
        // Do not hold guard while draining transport workers that may need it.
        // On a drain failure keep the observation accounted until close retries.
        transport.close();synchronized(guard){observation.close();released=true;}
    }
}
