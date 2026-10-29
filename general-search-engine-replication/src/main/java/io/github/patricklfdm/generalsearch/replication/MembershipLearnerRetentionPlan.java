package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private nonvoting source obligations. Projection/decoding does not establish
 * durability, a quorum, learner progress or permission to export. In particular,
 * this version has no narrowing API: an uncertain old endpoint stays required. */
final class MembershipLearnerRetentionPlan {
    static final int MAXIMUM=16384;
    private final String root;
    private final Map<String,Object> request;
    private final MembershipIdentity learner;
    private final List<MembershipCapsule.Anchor> possible;

    private MembershipLearnerRetentionPlan(String root,Map<String,Object> request,MembershipIdentity learner,
            List<MembershipCapsule.Anchor> possible) {
        MembershipValidation.digest(root);this.root=root;
        this.request=request==null?null:object(parse(canonical(request,8192),8192));this.learner=learner;
        this.possible=possible.stream().map(a->new MembershipCapsule.Anchor(
                object(parse(canonical(a.cut(),8192),8192)),a.catalog(),a.application())).toList();
        require((request==null)==(learner==null) && (request==null)==possible.isEmpty(),"learner retention empty binding");
        require(possible.size()<=2,"learner retention unresolved endpoint capacity");
        if(request!=null) {
            checkType(this.request,"request");
            require(root.equals(request.get("root")) && !request.get("kind").equals("REMOVE")
                    && list(request.get("target")).stream().map(MembershipFormat::object).map(MembershipContext::identity).anyMatch(learner::equals),
                    "learner retention exact request identity");
        }
        long prior=-1;
        for(var point:this.possible) {
            checkType(point.cut(),"cut");MembershipContext.checkView(object(point.cut().get("view")));
            MembershipValidation.digest(point.catalog());MembershipValidation.digest(point.application());
            require(index(point)>prior,"learner retention endpoint order");prior=index(point);
        }
    }
    private static long index(MembershipCapsule.Anchor point){return number(point.cut().get("index"));}
    boolean empty(){return request==null;}
    List<MembershipCapsule.Anchor> recorded(){return possible;}
    byte[] bytes() {
        var value=new TreeMap<String,Object>();value.put("root",root);value.put("request",request);
        value.put("learner",learner==null?null:MembershipPeerRetentionPlan.identity(learner));
        value.put("possible",possible.stream().map(MembershipRetentionIntent::anchor).toList());return canonical(value,MAXIMUM);
    }
    static MembershipLearnerRetentionPlan decode(byte[] bytes) {
        var value=object(parse(bytes,MAXIMUM));
        require(value.keySet().equals(Set.of("root","request","learner","possible")),"learner retention plan fields");
        var points=list(value.get("possible"));require(points.size()<=2,"learner retention unresolved endpoint capacity");
        var anchors=new ArrayList<MembershipCapsule.Anchor>();
        for(var item:points) {
            var a=object(item);require(a.keySet().equals(Set.of("cut","catalog","application")),"learner retention anchor fields");
            anchors.add(new MembershipCapsule.Anchor(object(a.get("cut")),(String)a.get("catalog"),(String)a.get("application")));
        }
        var identity=value.get("learner")==null?null:MembershipContext.identity(object(value.get("learner")));
        var plan=new MembershipLearnerRetentionPlan((String)value.get("root"),value.get("request")==null?null:object(value.get("request")),identity,anchors);
        require(Arrays.equals(bytes,plan.bytes()),"learner retention noncanonical plan");return plan;
    }
    static MembershipLearnerRetentionPlan genesis(MembershipCapsule capsule) {
        require(number(capsule.context.cut.get("index"))==0,"learner retention initialization requires genesis");
        return new MembershipLearnerRetentionPlan(capsule.context.root,null,null,List.of());
    }
    /** The actual owner authenticates this entire set before renewal/adoption. */
    List<MembershipCapsule.Anchor> required(MembershipCapsule current,byte[] ancestry) {
        require(root.equals(current.context.root),"learner retention foreign root");
        if(!empty()) {
            require(learner.equals(current.context.identities.get(learner.nodeId().value())),"learner retention identity changed");
            require(list(current.context.catalog.get("results")).stream().map(MembershipFormat::object)
                    .anyMatch(row->row.get("request").equals(request)),"learner retention original request missing");
        }
        current.verifyAncestry(ancestry,possible);return possible;
    }
    boolean preventsRetirement(String kind,byte[] payload) {
        return !empty() && kind.equals("RETIRE") && number(object(command(kind,payload)).get("through"))>=number(request.get("number"));
    }
    /** Record the exact complete source, not the prepared image's preceding cut.
     * A repeated offer is idempotent; a third uncertain endpoint is refused. */
    MembershipLearnerRetentionPlan offer(MembershipCapsule current,byte[] ancestry,MembershipIdentity joining) {
        required(current,ancestry);
        Map<String,Object> original;
        if(empty())original=MembershipLearnerDiscovery.reservation(current.context,joining);
        else {
            require(learner.equals(joining),"learner retention different operation identity");original=request;
        }
        var points=new TreeMap<Long,MembershipCapsule.Anchor>();possible.forEach(a->points.put(index(a),a));
        var previous=points.putIfAbsent(index(current.terminal()),current.terminal());
        require(previous==null || previous.equals(current.terminal()),"learner retention conflicting endpoint");
        return new MembershipLearnerRetentionPlan(root,original,joining,List.copyOf(points.values()));
    }
    /** Conservative source reconciliation only. No decoded claim can erase an
     * obligation, change its operation or turn same-index bytes into ancestry. */
    static MembershipLearnerRetentionPlan mergeRecorded(String root,List<MembershipLearnerRetentionPlan> originals) {
        require(!originals.isEmpty() && originals.size()<=7,"learner retention original count");
        MembershipLearnerRetentionPlan bound=null;var points=new TreeMap<Long,MembershipCapsule.Anchor>();
        for(var plan:originals) {
            require(root.equals(plan.root),"learner retention foreign root");if(plan.empty())continue;
            if(bound==null)bound=plan;
            require(bound.request.equals(plan.request) && bound.learner.equals(plan.learner),"learner retention conflicting original binding");
            for(var a:plan.possible) {
                var old=points.putIfAbsent(index(a),a);require(old==null || old.equals(a),"learner retention conflicting endpoint");
            }
        }
        return new MembershipLearnerRetentionPlan(root,bound==null?null:bound.request,bound==null?null:bound.learner,List.copyOf(points.values()));
    }
}
