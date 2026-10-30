package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Separate read-only route for an already prepared learner. A retained terminal
 * result or INTENT may be read, but never becomes admission, cleanup or a vote. */
final class MembershipLearnerProgressAccess {
    private MembershipLearnerProgressAccess() {}
    private static Map<String,Object> find(MembershipContext context,MembershipIdentity reader) {
        if(!reader.equals(context.identities.get(reader.nodeId().value())))return null;
        for(Object item:list(context.catalog.get("results"))) {
            var row=object(item);var request=object(row.get("request"));
            if(request.get("kind").equals("REMOVE") || row.get("prepared")==null)continue;
            var old=object(object(object(row.get("prepared")).get("cut")).get("view"));
            if(nodes(old,"old").contains(reader.nodeId().value()) || !list(request.get("target")).stream()
                    .map(MembershipFormat::object).map(MembershipContext::identity).anyMatch(reader::equals))continue;
            require(old.get("operation")==null && nodes(old,"old").equals(nodes(old,"new"))
                    && request.get("expected").equals(viewDigest(context.root,old)),"learner progress original stable preparation");
            require(Set.of("PREPARING","READY","SEALED","JOINT","COMPLETED","CANCELLED").contains(row.get("phase")),
                    "learner progress retained phase");
            return row;
        }
        return null;
    }
    static Map<String,Object> operation(MembershipContext context,MembershipIdentity reader) {
        var row=find(context,reader);require(row!=null,"learner progress missing retained prepared operation");return row;
    }
    /** A retained original operation may confirm its still-owned stable source
     * after JOINT publication. Only a permanent original voter can request it;
     * ordinary discovery remains restricted to the active pre-JOINT phase. */
    static Map<String,Object> headRequest(MembershipContext context,MembershipIdentity learner,MembershipIdentity voter) {
        require(voter.equals(context.identities.get(voter.nodeId().value())) && context.voters().contains(voter.nodeId().value()),
                "learner confirmation current original voter");
        var row=operation(context,learner);var original=object(row.get("request"));
        require(Set.of("JOINT","COMPLETED").contains(row.get("phase")),"learner confirmation published INTENT required");
        var old=object(object(object(row.get("prepared")).get("cut")).get("view"));
        require(nodes(old,"old").contains(voter.nodeId().value()),"learner confirmation requester not original voter");
        return original;
    }
    /** Pure binding check, not an export permit. After local publication the
     * joining identity may read the current prefix like any configured member;
     * this does not establish its local installation or voting eligibility. */
    static void publishedSource(MembershipCapsule current,byte[] ancestry,MembershipIdentity learner,
            MembershipIdentity source,MembershipLearnerRetentionPlan retained) {
        var context=current.context;var original=headRequest(context,learner,source);
        require(context.voters().contains(learner.nodeId().value()),"published learner not configured");
        var plan=object(parse(retained.bytes(),MembershipLearnerRetentionPlan.MAXIMUM));
        require(original.equals(plan.get("request")) && MembershipPeerRetentionPlan.identity(learner).equals(plan.get("learner")),
                "published learner original retained request");
        retained.required(current,ancestry);
    }
    static String reference(MembershipLearnerRequest learner,Map<String,Object> cut,String scope) {
        return reference(learner.root().manifestDigest(),learner.identity(),MembershipLearnerDiscovery.request(learner.change()),cut,scope);
    }
    private static String reference(String root,MembershipIdentity learner,Map<String,Object> request,Map<String,Object> cut,String scope) {
        require(MembershipLearnerPrefixExport.SCOPES.contains(scope),"learner progress scope");
        return hash(canonical(Map.of("schema","gse-v53-learner-progress-reference/1.3","root",root,
                "learner",MembershipBootstrapSeed.identity(learner),"request",request,"cut",cut,"scope",scope),16384));
    }
    static String scope(MembershipContext context,MembershipIdentity reader,String digest) {
        var row=find(context,reader);if(row==null)return null;
        for(String scope:MembershipLearnerPrefixExport.SCOPES)
            if(digest.equals(reference(context.root,reader,object(row.get("request")),context.cut,scope)))return scope;
        return null;
    }
    static void original(MembershipContext context,MembershipLearnerRequest request,MembershipIdentity source) {
        var row=operation(context,request.identity());
        require(context.root.equals(request.root().manifestDigest())
                && row.get("request").equals(MembershipLearnerDiscovery.request(request.change()))
                && source.equals(context.identities.get(source.nodeId().value())) && context.voters().contains(source.nodeId().value()),
                "learner progress exact original request/source");
    }
}
