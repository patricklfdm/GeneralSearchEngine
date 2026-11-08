package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Private nonvoting source obligations. Projection/decoding does not establish
 * durability, a quorum, learner progress or permission to export. Narrowing
 * requires an actual live forced head, never a decoded endpoint or receipt. */
final class MembershipLearnerRetentionPlan {
    static final int MAXIMUM=16384;
    private final String root;
    private final Map<String,Object> request;
    private final MembershipIdentity learner;
    private final List<MembershipCapsule.Anchor> possible;
    private final List<MembershipCapsule.Anchor> renewals;
    private final MembershipLearnerConfirmation confirmation;

    private MembershipLearnerRetentionPlan(String root,Map<String,Object> request,MembershipIdentity learner,
            List<MembershipCapsule.Anchor> possible) {
        this(root,request,learner,possible,null,List.of());
    }
    private MembershipLearnerRetentionPlan(String root,Map<String,Object> request,MembershipIdentity learner,
            List<MembershipCapsule.Anchor> possible,MembershipLearnerConfirmation confirmation,List<MembershipCapsule.Anchor> renewals) {
        MembershipValidation.digest(root);this.root=root;
        this.confirmation=confirmation;
        this.request=request==null?null:object(parse(canonical(request,8192),8192));this.learner=learner;
        this.possible=possible.stream().map(a->new MembershipCapsule.Anchor(
                object(parse(canonical(a.cut(),8192),8192)),a.catalog(),a.application())).toList();
        this.renewals=renewals.stream().map(a->new MembershipCapsule.Anchor(
                object(parse(canonical(a.cut(),8192),8192)),a.catalog(),a.application())).toList();
        require((request==null)==(learner==null) && (request==null)==possible.isEmpty(),"learner retention empty binding");
        require(possible.size()<=2,"learner retention unresolved endpoint capacity");
        require(renewals.size()<=2 && (renewals.isEmpty() || !possible.isEmpty()),"learner retention pending renewal capacity");
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
        prior=-1;
        for(var point:this.renewals) {
            checkType(point.cut(),"cut");MembershipContext.checkView(object(point.cut().get("view")));
            MembershipValidation.digest(point.catalog());MembershipValidation.digest(point.application());
            require(index(point)>prior && index(point)<index(this.possible.getFirst()),"learner retention pending renewal order");prior=index(point);
        }
        if(confirmation!=null) {
            require(request!=null && confirmation.endpoint.equals(this.possible.getFirst()),"learner confirmation retained endpoint");
            confirmation.binding(root,this.request,learner);
        }
    }
    private static long index(MembershipCapsule.Anchor point){return number(point.cut().get("index"));}
    boolean empty(){return request==null;}
    List<MembershipCapsule.Anchor> recorded(){return possible;}
    byte[] bytes() {
        var value=new TreeMap<String,Object>();value.put("root",root);value.put("request",request);
        value.put("learner",learner==null?null:MembershipPeerRetentionPlan.identity(learner));
        value.put("possible",possible.stream().map(MembershipRetentionIntent::anchor).toList());
        if(!renewals.isEmpty())value.put("renewals",renewals.stream().map(MembershipRetentionIntent::anchor).toList());
        if(confirmation!=null)value.put("confirmation",confirmation.value());return canonical(value,MAXIMUM);
    }
    static MembershipLearnerRetentionPlan decode(byte[] bytes) {
        var value=object(parse(bytes,MAXIMUM));
        require(value.keySet().containsAll(Set.of("root","request","learner","possible"))
                && Set.of("root","request","learner","possible","confirmation","renewals").containsAll(value.keySet()),"learner retention plan fields");
        var points=list(value.get("possible"));require(points.size()<=2,"learner retention unresolved endpoint capacity");
        var anchors=new ArrayList<MembershipCapsule.Anchor>();
        for(var item:points) {
            var a=object(item);require(a.keySet().equals(Set.of("cut","catalog","application")),"learner retention anchor fields");
            anchors.add(new MembershipCapsule.Anchor(object(a.get("cut")),(String)a.get("catalog"),(String)a.get("application")));
        }
        var identity=value.get("learner")==null?null:MembershipContext.identity(object(value.get("learner")));
        var proof=value.containsKey("confirmation")?MembershipLearnerConfirmation.decodeValue(object(value.get("confirmation"))):null;
        var renewals=new ArrayList<MembershipCapsule.Anchor>();
        if(value.containsKey("renewals")) {
            var items=list(value.get("renewals"));require(!items.isEmpty() && items.size()<=2,"learner retention pending renewal capacity");
            for(var item:items) {
                var a=object(item);require(a.keySet().equals(Set.of("cut","catalog","application")),"learner renewal anchor fields");
                renewals.add(new MembershipCapsule.Anchor(object(a.get("cut")),(String)a.get("catalog"),(String)a.get("application")));
            }
        }
        var plan=new MembershipLearnerRetentionPlan((String)value.get("root"),value.get("request")==null?null:object(value.get("request")),identity,anchors,proof,renewals);
        require(Arrays.equals(bytes,plan.bytes()),"learner retention noncanonical plan");return plan;
    }
    static MembershipLearnerRetentionPlan genesis(MembershipCapsule capsule) {
        require(number(capsule.context.cut.get("index"))==0,"learner retention initialization requires genesis");
        return new MembershipLearnerRetentionPlan(capsule.context.root,null,null,List.of());
    }
    /** The actual owner authenticates this entire set before renewal/adoption. */
    List<MembershipCapsule.Anchor> required(MembershipCapsule current,byte[] ancestry) {
        var retained=requiredContext(current);current.verifyAncestry(ancestry,retained);return retained;
    }
    List<MembershipCapsule.Anchor> required(MembershipCapsule current,MembershipCapsule.CheckedAncestry ancestry) {
        var retained=requiredContext(current);ancestry.require(current,retained);return retained;
    }
    private List<MembershipCapsule.Anchor> requiredContext(MembershipCapsule current) {
        require(root.equals(current.context.root),"learner retention foreign root");
        if(!empty()) {
            require(learner.equals(current.context.identities.get(learner.nodeId().value())),"learner retention identity changed");
            require(list(current.context.catalog.get("results")).stream().map(MembershipFormat::object)
                    .anyMatch(row->row.get("request").equals(request)),"learner retention original request missing");
        }
        if(confirmation!=null)confirmation.identities(current.context);
        var retained=new ArrayList<>(renewals);retained.addAll(possible);
        return List.copyOf(retained);
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
        return new MembershipLearnerRetentionPlan(root,original,joining,List.copyOf(points.values()),confirmation,renewals);
    }
    /** A local confirmation is not a replicated discharge. Continue forcing
     * the old checkpoint statements while another voter may still require
     * them. Only selected-source reconciliation can retire this bounded debt. */
    private List<MembershipCapsule.Anchor> pendingRenewals(long through) {
        var retained=new TreeMap<Long,MembershipCapsule.Anchor>();renewals.forEach(a->retained.put(index(a),a));
        possible.stream().filter(a->index(a)<through).forEach(a->retained.put(index(a),a));
        return List.copyOf(retained.values());
    }
    /** A real local forced head may discharge older uncertainty. Preserve any
     * later offered point: observing the old head does not disprove its receipt.
     * A late old observation cannot reintroduce an already discharged point. */
    MembershipLearnerRetentionPlan observe(MembershipCapsule current,byte[] ancestry,
            MembershipLearnerHeadObservation observed)throws java.io.IOException {
        Objects.requireNonNull(observed);observed.check();required(current,ancestry);
        require(!empty() && learner.equals(observed.learner) && request.equals(observed.request),"learner observation original binding");
        current.verifyAncestry(ancestry,List.of(observed.endpoint));
        long at=index(observed.endpoint);
        if(at<index(possible.getFirst()))return this;
        // Another source owner may have recorded and served this head. The
        // actual forced observation plus original ancestry, not membership in
        // this local offer list, establishes its endpoint.
        for(var point:possible)if(index(point)==at)require(point.equals(observed.endpoint),"learner observation conflicting endpoint");
        var remaining=new ArrayList<MembershipCapsule.Anchor>();remaining.add(observed.endpoint);
        possible.stream().filter(a->index(a)>at).forEach(remaining::add);observed.check();
        // Local-only observations do not invent a network transcript. A newer
        // local head can narrow locally, but must be queried before that new
        // narrowing can discharge another source's frozen uncertainty.
        return new MembershipLearnerRetentionPlan(root,request,learner,remaining,
                confirmation!=null && confirmation.endpoint.equals(observed.endpoint)?confirmation:null,pendingRenewals(at));
    }
    /** Pure projection; the native journal obtains evidence only from the live
     * original probe. Decoding a transcript cannot install this plan. */
    MembershipLearnerRetentionPlan confirm(MembershipCapsule current,byte[] ancestry,MembershipLearnerConfirmation proof) {
        required(current,ancestry);require(!empty(),"learner confirmation unbound plan");
        proof.binding(root,request,learner);proof.identities(current.context);current.verifyAncestry(ancestry,List.of(proof.endpoint));
        long at=index(proof.endpoint);if(at<index(possible.getFirst()))return this;
        for(var point:possible)if(index(point)==at)require(point.equals(proof.endpoint),"learner confirmation conflicting endpoint");
        if(confirmation!=null && confirmation.endpoint.equals(proof.endpoint))return this;
        var remaining=new ArrayList<MembershipCapsule.Anchor>();remaining.add(proof.endpoint);
        possible.stream().filter(a->index(a)>at).forEach(remaining::add);
        return new MembershipLearnerRetentionPlan(root,request,learner,remaining,proof,pendingRenewals(at));
    }
    /** Conservative source reconciliation only. No decoded claim can erase an
     * obligation, change its operation or turn same-index bytes into ancestry. */
    static MembershipLearnerRetentionPlan mergeRecorded(String root,List<MembershipLearnerRetentionPlan> originals) {
        return merge(root,originals,null);
    }
    /** Only the selected-source verifier can construct this provenance token.
     * Arbitrary decoded plans keep using the conservative entry above. */
    static MembershipLearnerRetentionPlan mergeSelected(String root,MembershipSelectedLearnerRetention.Originals originals) {
        Objects.requireNonNull(originals);return merge(root,originals.plans,originals.authority);
    }
    private static MembershipLearnerRetentionPlan merge(String root,List<MembershipLearnerRetentionPlan> originals,MembershipContext authority) {
        require(!originals.isEmpty() && originals.size()<=7,"learner retention original count");
        MembershipLearnerRetentionPlan bound=null;var points=new TreeMap<Long,MembershipCapsule.Anchor>();MembershipLearnerConfirmation proof=null;
        for(var plan:originals) {
            require(root.equals(plan.root),"learner retention foreign root");if(plan.empty())continue;
            if(bound==null)bound=plan;
            require(bound.request.equals(plan.request) && bound.learner.equals(plan.learner),"learner retention conflicting original binding");
            var retained=new ArrayList<>(plan.renewals);retained.addAll(plan.possible);
            for(var a:retained) {
                var old=points.putIfAbsent(index(a),a);require(old==null || old.equals(a),"learner retention conflicting endpoint");
            }
            if(authority!=null && plan.confirmation!=null) {
                var candidate=plan.confirmation;candidate.identities(authority);
                if(proof==null || index(candidate.endpoint)>index(proof.endpoint)
                        || index(candidate.endpoint)==index(proof.endpoint) && candidate.digest().compareTo(proof.digest())<0)proof=candidate;
            }
        }
        // Check conflicts above even for points that will be discharged. Do
        // not let a newer watermark hide same-index divergent authority.
        if(proof!=null)points.headMap(index(proof.endpoint),false).clear();
        return new MembershipLearnerRetentionPlan(root,bound==null?null:bound.request,bound==null?null:bound.learner,List.copyOf(points.values()),proof,List.of());
    }
}
