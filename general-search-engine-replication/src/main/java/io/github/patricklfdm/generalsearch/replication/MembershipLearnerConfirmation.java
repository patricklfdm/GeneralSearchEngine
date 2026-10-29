package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact original wire evidence. Decoding validates binding, not receipt or
 * durability: only a live probe may install it, and only force-bound selected
 * originals may use its watermark when merging. Checksums are not signatures. */
final class MembershipLearnerConfirmation {
    static final int MAXIMUM=8192;
    private final Map<String,Object> encoded;
    private final Decoded query,ack;
    final MembershipCapsule.Anchor endpoint;
    private MembershipLearnerConfirmation(Map<String,Object> value) {
        require(value.keySet().equals(Set.of("query","ack")),"learner confirmation fields");
        encoded=object(parse(canonical(value,MAXIMUM),MAXIMUM));
        query=wire("query","LEARNER_HEAD_QUERY");ack=wire("ack","LEARNER_HEAD_ACK");
        var point=object(object(ack.value().get("payload")).get("endpoint"));
        endpoint=new MembershipCapsule.Anchor(object(point.get("cut")),(String)point.get("catalog"),(String)point.get("application"));
    }
    private Decoded wire(String field,String kind) {
        require(encoded.get(field) instanceof String,"learner confirmation wire encoding");String text=(String)encoded.get(field);
        byte[] bytes=Base64.getDecoder().decode(text);require(Base64.getEncoder().encodeToString(bytes).equals(text),"learner confirmation canonical base64");
        return decode(bytes,"wire",kind);
    }
    static MembershipLearnerConfirmation decodeValue(Map<String,Object> value){return new MembershipLearnerConfirmation(value);}
    static MembershipLearnerConfirmation received(Decoded query,Decoded ack) {
        return decodeValue(Map.of("query",Base64.getEncoder().encodeToString(query.bytes()),"ack",Base64.getEncoder().encodeToString(ack.bytes())));
    }
    Map<String,Object> value(){return encoded;}
    String digest(){return hash(canonical(encoded,MAXIMUM));}
    void binding(String root,Map<String,Object> request,MembershipIdentity learner) {
        var q=query.value();var sender=MembershipContext.identity(object(q.get("sender")));
        MembershipWire.envelope(query,root,sender,learner);MembershipWire.envelope(ack,root,learner,sender);
        MembershipWire.correlated(query,ack,"LEARNER_HEAD_ACK");
        var view=object(endpoint.cut().get("view"));MembershipContext.checkView(view);
        require(!sender.equals(learner) && q.get("view").equals(request.get("expected"))
                && q.get("ballot").equals(MembershipLearnerDiscovery.correlation(learner)) && number(q.get("sequence"))==1
                && object(q.get("payload")).get("request").equals(request)
                && object(ack.value().get("payload")).get("request").equals(hash(canonical(request,8192)))
                && view.get("operation")==null && MembershipContext.nodes(view,"old").contains(sender.nodeId().value())
                && !MembershipContext.nodes(view,"old").contains(learner.nodeId().value())
                && MembershipContext.viewDigest(root,view).equals(request.get("expected")),"learner confirmation original binding");
    }
    void identities(MembershipContext context) {
        for(String field:List.of("sender","recipient")) {
            var identity=MembershipContext.identity(object(query.value().get(field)));
            require(identity.equals(context.identities.get(identity.nodeId().value())),"learner confirmation permanent identity");
        }
    }
}
