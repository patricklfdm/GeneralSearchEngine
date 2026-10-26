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
