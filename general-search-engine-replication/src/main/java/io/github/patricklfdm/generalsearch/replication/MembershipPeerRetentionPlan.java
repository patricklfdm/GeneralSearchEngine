package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Pure peer-endpoint retention projection. This is NOT a durable receipt or permission
 * to dispatch. A runtime must persist/replicate its intent before exposure and recover
 * the same uncertainty through selected sources. No public runtime uses this class yet. */
final class MembershipPeerRetentionPlan {
    private record Peer(MembershipIdentity identity, List<MembershipCapsule.Anchor> possible) {
        Peer {
            Objects.requireNonNull(identity);possible=possible.stream().map(a->new MembershipCapsule.Anchor(
                    object(parse(canonical(a.cut(),16384),16384)),a.catalog(),a.application())).toList();
            require(!possible.isEmpty() && possible.size()<=2,"peer retention unresolved endpoint capacity");
            long previous=-1;
            for(var anchor:possible) {
                checkType(anchor.cut(),"cut");MembershipContext.checkView(object(anchor.cut().get("view")));
                MembershipValidation.digest(anchor.catalog());MembershipValidation.digest(anchor.application());
                require(index(anchor)>previous,"peer retention endpoint order");previous=index(anchor);
            }
        }
    }
    private final String root;
    private final Map<String,Object> view;
    private final SortedMap<String,Peer> peers;
    private MembershipPeerRetentionPlan(String root,Map<String,Object> view,Map<String,Peer> peers) {
        MembershipValidation.digest(root);MembershipContext.checkView(view);
        this.root=root;this.view=object(parse(canonical(view,16384),16384));
        this.peers=Collections.unmodifiableSortedMap(new TreeMap<>(peers));
        var voters=new TreeSet<String>(MembershipContext.nodes(view,"old"));voters.addAll(MembershipContext.nodes(view,"new"));
        require(this.peers.keySet().equals(voters) && peers.size()<=6,"peer retention exact governing identities");
        peers.forEach((name,peer)->require(name.equals(peer.identity.nodeId().value()),"peer retention identity key"));
    }
    private static long viewPosition(Map<String,Object> view){return 2*number(view.get("generation"))+(view.get("operation")==null?0:1);}
    private static long index(MembershipCapsule.Anchor anchor){return number(anchor.cut().get("index"));}
    static Map<String,Object> identity(MembershipIdentity id) {
        return Map.of("node",id.nodeId().value(),"storage",id.storageId().toString(),
                "host",id.endpoint().host(),"port",(long)id.endpoint().port());
    }
    /** Private canonical metadata, never a capsule, voter receipt or remote proof. */
    byte[] bytes() {
        var rows=new ArrayList<Object>();
        for(var peer:peers.values())rows.add(Map.of("identity",identity(peer.identity),"possible",peer.possible.stream()
                .map(a->Map.of("cut",a.cut(),"catalog",a.catalog(),"application",a.application())).toList()));
        return canonical(Map.of("root",root,"view",view,"peers",rows),32768);
    }
    static MembershipPeerRetentionPlan decode(byte[] bytes) {
        var value=object(parse(bytes,32768));require(value.keySet().equals(Set.of("root","view","peers")),"peer retention plan fields");
        var rows=list(value.get("peers"));require(rows.size()>=3 && rows.size()<=6,"peer retention plan count");
        var peers=new TreeMap<String,Peer>();String prior="";
        for(var row:rows) {
            var p=object(row);require(p.keySet().equals(Set.of("identity","possible")),"peer retention peer fields");
            var encoded=object(p.get("identity"));var id=MembershipContext.identity(encoded);
            require(encoded.equals(identity(id)),"peer retention identity fields");String name=id.nodeId().value();
            require(name.compareTo(prior)>0,"peer retention peer order");prior=name;
            var points=list(p.get("possible"));require(!points.isEmpty() && points.size()<=2,"peer retention point count");
            var anchors=new ArrayList<MembershipCapsule.Anchor>();
            for(var point:points) {
                var a=object(point);require(a.keySet().equals(Set.of("cut","catalog","application")),"peer retention anchor fields");
                anchors.add(new MembershipCapsule.Anchor(object(a.get("cut")),(String)a.get("catalog"),(String)a.get("application")));
            }
            peers.put(name,new Peer(id,anchors));
        }
        var plan=new MembershipPeerRetentionPlan((String)value.get("root"),object(value.get("view")),peers);
        require(Arrays.equals(bytes,plan.bytes()),"peer retention noncanonical plan");return plan;
    }
    /** Initial identities and their common state come from the authenticated genesis. */
    static MembershipPeerRetentionPlan genesis(MembershipCapsule capsule) {
        require(number(capsule.context.cut.get("index"))==0,"peer retention initialization requires genesis");
        var peers=new TreeMap<String,Peer>();
        for(String node:capsule.context.voters())peers.put(node,new Peer(capsule.context.identities.get(node),List.of(capsule.terminal())));
        return new MembershipPeerRetentionPlan(capsule.context.root,capsule.context.view,peers);
    }
    private void context(MembershipCapsule current,byte[] ancestry,boolean sameView) {
        require(root.equals(current.context.root),"peer retention foreign root");
        require(viewPosition(current.context.view)>=viewPosition(view),"peer retention configuration rollback");
        if(sameView)require(view.equals(current.context.view),"peer retention configuration reconciliation required");
        for(var peer:peers.values())require(peer.identity.equals(current.context.identities.get(peer.identity.nodeId().value())),"peer retention identity changed");
        current.verifyAncestry(ancestry,anchors());
    }
    private List<MembershipCapsule.Anchor> anchors() {
        var ordered=new TreeMap<Long,MembershipCapsule.Anchor>();
        for(var peer:peers.values())for(var anchor:peer.possible) {
            var previous=ordered.putIfAbsent(index(anchor),anchor);
            require(previous==null || previous.equals(anchor),"peer retention conflicting history endpoint");
        }
        return List.copyOf(ordered.values());
    }
    List<MembershipCapsule.Anchor> required(MembershipCapsule current,byte[] ancestry) {
        context(current,ancestry,false);return anchors();
    }
    void capture(MembershipCapsule current,byte[] ancestry){context(current,ancestry,true);}
    /** Metadata projection only; the installation must authenticate these anchors. */
    List<MembershipCapsule.Anchor> recorded(){return anchors();}
    static MembershipPeerRetentionPlan mergeRecorded(String root,Map<String,Object> view,List<MembershipPeerRetentionPlan> originals) {
        require(!originals.isEmpty() && originals.size()<=7,"selected retention local/source count");
        var first=originals.getFirst();var union=new TreeMap<String,TreeMap<Long,MembershipCapsule.Anchor>>();
        first.peers.keySet().forEach(n->union.put(n,new TreeMap<>()));
        for(var plan:originals) {
            require(plan.root.equals(root) && plan.view.equals(view) && plan.peers.keySet().equals(first.peers.keySet()),"selected retention original root/view");
            for(var row:plan.peers.entrySet()) {
                require(row.getValue().identity.equals(first.peers.get(row.getKey()).identity),"selected retention original identity");
                for(var anchor:row.getValue().possible) {
                    var previous=union.get(row.getKey()).putIfAbsent(index(anchor),anchor);
                    require(previous==null || previous.equals(anchor),"selected retention conflicting endpoint");
                }
            }
        }
        var peers=new TreeMap<String,Peer>();union.forEach((n,points)->peers.put(n,new Peer(first.peers.get(n).identity,List.copyOf(points.values()))));
        return new MembershipPeerRetentionPlan(root,view,peers);
    }
    List<MembershipCapsule.Anchor> possible(MembershipIdentity peer) {
        var value=peers.get(peer.nodeId().value());require(value!=null && value.identity.equals(peer),"peer retention unknown identity");
        return value.possible;
    }
    /** The future sender must force this result before allowing that target to install.
     * No second target is admitted while any earlier dispatch remains ambiguous. */
    MembershipPeerRetentionPlan dispatch(MembershipCapsule current,byte[] ancestry,MembershipIdentity peer) {
        context(current,ancestry,true);var old=possible(peer);
        require(old.size()==1,"peer retention unresolved dispatch");
        require(index(old.getFirst())<index(current.terminal()),"peer retention target must advance");
        var next=new TreeMap<>(peers);next.put(peer.nodeId().value(),new Peer(peer,List.of(old.getFirst(),current.terminal())));
        return new MembershipPeerRetentionPlan(root,view,next);
    }
    /** Conservative remote intent at this owner's already authenticated current
     * target. A locally confirmed newer endpoint need not be regressed by a late
     * identical request. Imported claims alone can never discard a lower point. */
    MembershipPeerRetentionPlan recordDispatch(MembershipCapsule current,byte[] ancestry,MembershipIdentity peer,
            MembershipCapsule.Anchor lower,MembershipCapsule.Anchor upper) {
        context(current,ancestry,true);
        require(upper.equals(current.terminal()) && index(lower)<index(upper),"retention intent exact advancing target");
        return recordCoveredDispatch(current,ancestry,peer,lower,upper);
    }
    /** Promote an independently retained possible target only after the actual
     * current generation covers it. Old-view obligations survive through FINAL
     * until the existing explicit configuration reconciliation runs. */
    MembershipPeerRetentionPlan recordCoveredDispatch(MembershipCapsule current,byte[] ancestry,MembershipIdentity peer,
            MembershipCapsule.Anchor lower,MembershipCapsule.Anchor upper) {
        context(current,ancestry,false);
        require(index(lower)<index(upper) && index(upper)<=index(current.terminal()),"retention covered target must advance");
        current.verifyAncestry(ancestry,List.of(lower,upper));
        return projectCoveredDispatch(peer,lower,upper,current.context.cut);
    }
    /** Pure included-source projection. The resulting plan is not authority:
     * generation installation must authenticate every recorded endpoint first. */
    MembershipPeerRetentionPlan projectCoveredDispatch(MembershipIdentity peer,MembershipCapsule.Anchor lower,
            MembershipCapsule.Anchor upper,Map<String,Object> selectedCut) {
        require(index(lower)<index(upper) && index(upper)<=number(selectedCut.get("index")),"projected retention covered target");
        var old=possible(peer);
        var points=new TreeMap<Long,MembershipCapsule.Anchor>();old.forEach(a->points.put(index(a),a));
        for(var anchor:List.of(lower,upper)) {
            if(index(anchor)<points.firstKey())continue;
            var existing=points.putIfAbsent(index(anchor),anchor);
            require(existing==null || existing.equals(anchor),"retention intent conflicting endpoint");
        }
        var next=new TreeMap<>(peers);next.put(peer.nodeId().value(),new Peer(peer,List.copyOf(points.values())));
        return new MembershipPeerRetentionPlan(root,view,next);
    }
    private static void copy(MembershipCapsule current,byte[] ancestry,MembershipFloor.Copy copy) {
        Objects.requireNonNull(copy).check();
        require(copy.capsule.context.root.equals(current.context.root) && copy.owner.equals(current.context.identities.get(copy.owner.nodeId().value()))
                && current.context.voters().contains(copy.owner.nodeId().value()),"peer retention foreign/non-governing copy");
        current.verifyAncestry(ancestry,List.of(copy.capsule.terminal()));
    }
    /** An actual newer complete copy rules out older states, but an old copy cannot
     * cancel a still-in-flight target. STATUS and arbitrary cut maps are not inputs. */
    MembershipPeerRetentionPlan observe(MembershipCapsule current,byte[] ancestry,MembershipFloor.Copy copy) {
        context(current,ancestry,true);copy(current,ancestry,copy);var old=possible(copy.owner);var observed=copy.capsule.terminal();
        if(index(observed)<index(old.getFirst()))return this;
        var next=new TreeMap<>(peers);var endpoints=new ArrayList<MembershipCapsule.Anchor>();endpoints.add(observed);
        for(var anchor:old)if(index(anchor)>index(observed))endpoints.add(anchor);
        else if(index(anchor)==index(observed))require(anchor.equals(observed),"peer retention conflicting observed endpoint");
        next.put(copy.owner.nodeId().value(),new Peer(copy.owner,endpoints));return new MembershipPeerRetentionPlan(root,view,next);
    }
    /** Conservative selected-state merge. A purported higher endpoint in another
     * plan never erases a lower possibility. Only actual complete-copy observations
     * can narrow the union; exceeding two points refuses before any mutation. */
    static MembershipPeerRetentionPlan merge(MembershipCapsule current,byte[] ancestry,
            List<MembershipPeerRetentionPlan> originals,List<MembershipFloor.Copy> observations) {
        require(!originals.isEmpty() && originals.size()<=6 && observations.size()<=6,"peer retention merge input capacity");
        var union=new TreeMap<String,TreeMap<Long,MembershipCapsule.Anchor>>();
        for(String node:current.context.voters())union.put(node,new TreeMap<>());
        for(var original:originals) {
            original.context(current,ancestry,true);
            for(var entry:original.peers.entrySet())for(var anchor:entry.getValue().possible) {
                var previous=union.get(entry.getKey()).putIfAbsent(index(anchor),anchor);
                require(previous==null || previous.equals(anchor),"peer retention conflicting imported endpoint");
            }
        }
        var seen=new HashSet<String>();
        for(var observation:observations) {
            copy(current,ancestry,observation);String node=observation.owner.nodeId().value();require(seen.add(node),"peer retention duplicate copy observation");
            var observed=observation.capsule.terminal();var points=union.get(node);long at=index(observed);
            // Never regress already recorded knowledge using a stale observation.
            if(at<points.firstKey())continue;
            var same=points.get(at);require(same==null || same.equals(observed),"peer retention conflicting merge observation");
            points.headMap(at,true).clear();points.put(at,observed);
        }
        var next=new TreeMap<String,Peer>();
        union.forEach((node,points)->next.put(node,new Peer(current.context.identities.get(node),List.copyOf(points.values()))));
        return new MembershipPeerRetentionPlan(current.context.root,current.context.view,next);
    }
    /** Reconcile only an already authenticated configuration transition. New voters
     * require their actual complete current materialization; proposed targets do not
     * enter this method. Removed identities leave only after stable FINAL. */
    Set<String> joining(MembershipCapsule current,byte[] ancestry) {
        context(current,ancestry,false);var added=new TreeSet<>(current.context.voters());added.removeAll(peers.keySet());
        require(added.size()<=1,"peer retention joining identity capacity");return Collections.unmodifiableSet(added);
    }
    MembershipPeerRetentionPlan reconcile(MembershipCapsule current,byte[] ancestry,List<MembershipFloor.Copy> joining) {
        context(current,ancestry,false);require(joining.size()<=1,"peer retention joining copy count");
        var wanted=current.context.voters();var removed=new HashSet<>(peers.keySet());removed.removeAll(wanted);
        require(removed.isEmpty() || current.context.view.get("operation")==null,"peer retention removal before stable FINAL");
        var added=new HashSet<>(wanted);added.removeAll(peers.keySet());
        require(added.size()==joining.size() && added.size()<=1,"peer retention missing/extra joining copy");
        var next=new TreeMap<>(peers);removed.forEach(next::remove);
        for(var observation:joining) {
            copy(current,ancestry,observation);String node=observation.owner.nodeId().value();
            require(added.contains(node) && observation.capsule.terminal().equals(current.terminal()),"peer retention learner not installed at current cut");
            next.put(node,new Peer(observation.owner,List.of(observation.capsule.terminal())));
        }
        return new MembershipPeerRetentionPlan(root,current.context.view,next);
    }
}
