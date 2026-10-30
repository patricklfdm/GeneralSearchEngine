package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Immutable initial-ledger calculation for an unused joining owner. Exact
 * frozen old-majority originals are retained for replay. This value grants no
 * voting, dispatch, ledger installation or deletion authority. */
final class MembershipJoiningRetentionSeed {
    static final int MAXIMUM=FRAME;
    static final int FRAGMENT_MAXIMUM=2*1024*1024;
    private static final String SCHEMA="gse-v53-joining-retention-seed/1.3";
    private final byte[] bytes;
    final MembershipPeerRetentionPlan peers;
    final MembershipLearnerRetentionPlan learner;
    private MembershipJoiningRetentionSeed(byte[] bytes,MembershipPeerRetentionPlan peers,MembershipLearnerRetentionPlan learner) {
        this.bytes=bytes.clone();this.peers=peers;this.learner=learner;
    }
    byte[] bytes(){return bytes.clone();}
    static MembershipJoiningRetentionSeed capture(MembershipCapsule current,byte[] ancestry,MembershipIdentity joining,
            List<MembershipSelection.Source> sources) {
        require(sources.size()>=2 && sources.size()<=5,"joining retention old source count");
        var rows=new ArrayList<byte[]>();
        for(var source:sources)rows.add(fragment(source));
        return assemble(current,ancestry,joining,rows);
    }
    /** One frozen owner's original bytes. No quorum or remote authority. */
    static byte[] fragment(MembershipSelection.Source source) {
        var peer=MembershipPeerRetentionSource.read(source);var learner=MembershipLearnerRetentionSource.read(source);
        // The first initializer is intentionally limited to a settled old
        // majority. An unpublished future is never converted to an empty
        // ledger; that requires a separate carried-vote transaction.
        require(peer.proofs().isEmpty(),"joining retention unsettled future");
        return canonical(Map.of("basis",base(source.basis.bytes()),"envelope",base(source.capsule.packet.envelope()),
                "peers",base(MembershipPeerRetentionSource.wrapper(peer)),
                "learner",base(MembershipLearnerRetentionSource.wrapper(learner))),FRAGMENT_MAXIMUM);
    }
    static Decoded fragmentBasis(byte[] bytes) {
        require(bytes.length<=FRAGMENT_MAXIMUM,"joining retention fragment capacity");var row=object(parse(bytes,FRAGMENT_MAXIMUM));
        require(row.keySet().equals(Set.of("basis","envelope","peers","learner")) && Arrays.equals(bytes,canonical(row,FRAGMENT_MAXIMUM)),
                "joining retention canonical fragment");return decode(unbase(row.get("basis"),16384),"records","BASIS");
    }
    /** Used only while a network acquisition still owns and checks its received
     * originals. Decoding this value alone is never an installation permit. */
    static MembershipJoiningRetentionSeed assemble(MembershipCapsule current,byte[] ancestry,MembershipIdentity joining,List<byte[]> fragments) {
        require(fragments.size()>=2 && fragments.size()<=5,"joining retention old source count");var rows=new ArrayList<Object>();
        for(byte[] bytes:fragments){fragmentBasis(bytes);rows.add(parse(bytes,FRAGMENT_MAXIMUM));}
        return read(canonical(Map.of("schema",SCHEMA,"root",current.context.root,
                "joining",MembershipPeerRetentionPlan.identity(joining),"cut",current.context.cut,
                "catalog",current.terminal().catalog(),"application",current.terminal().application(),"sources",rows),MAXIMUM),
                current,ancestry,joining);
    }
    /** Replays the exact included bytes; decoded output is still not authority.
     * Uncertainty is unioned, never narrowed from a claimed higher endpoint. */
    static MembershipJoiningRetentionSeed read(byte[] bytes,MembershipCapsule current,byte[] ancestry,MembershipIdentity joining) {
        require(bytes.length<=MAXIMUM,"joining retention total capacity");var value=object(parse(bytes,MAXIMUM));
        require(value.keySet().equals(Set.of("schema","root","joining","cut","catalog","application","sources"))
                && SCHEMA.equals(value.get("schema")) && Arrays.equals(bytes,canonical(value,MAXIMUM)),"joining retention canonical fields");
        var context=current.context;var old=MembershipContext.nodes(context.view,"old");var next=MembershipContext.nodes(context.view,"new");
        String joiningNode=joining.nodeId().value();
        require(context.view.get("operation")!=null && !old.contains(joiningNode) && next.contains(joiningNode)
                && joining.equals(context.identities.get(joiningNode)),"joining retention exact new joint identity");
        require(context.root.equals(value.get("root")) && MembershipPeerRetentionPlan.identity(joining).equals(value.get("joining"))
                && context.cut.equals(value.get("cut")) && current.terminal().catalog().equals(value.get("catalog"))
                && current.terminal().application().equals(value.get("application")),"joining retention original installation binding");
        var rows=list(value.get("sources"));require(rows.size()>old.size()/2 && rows.size()<=old.size(),"joining retention old majority required");
        var peers=new ArrayList<MembershipPeerRetentionPlan>();var learners=new ArrayList<MembershipLearnerRetentionPlan>();
        String previous="";Object ballot=null;
        for(var item:rows) {
            var row=object(item);require(row.keySet().equals(Set.of("basis","envelope","peers","learner")),"joining retention source fields");
            var basis=decode(unbase(row.get("basis"),16384),"records","BASIS");var fields=basis.value();String node=(String)fields.get("voter");
            require(node.compareTo(previous)>0 && old.contains(node),"joining retention distinct ordered old voters");previous=node;
            require(fields.get("root").equals(context.root) && fields.get("cut").equals(context.cut)
                    && fields.get("view").equals(context.authority()),"joining retention exact joint source cut");
            context.ballot(fields.get("ballot"),true);
            require(ballot==null || ballot.equals(fields.get("ballot")),"joining retention mixed ballots");ballot=fields.get("ballot");
            require(fields.get("accepted")==null,"joining retention unsettled accepted tail");
            var identity=context.identities.get(node);byte[] envelope=unbase(row.get("envelope"),MembershipSourcePacket.ENVELOPE);
            var peer=MembershipPeerRetentionSource.included(envelope,basis,identity,unbase(row.get("peers"),MembershipPeerRetentionSource.MAXIMUM));
            var learner=MembershipLearnerRetentionSource.included(envelope,basis,identity,unbase(row.get("learner"),MembershipLearnerRetentionSource.MAXIMUM));
            // Included envelopes bind the original inventory and BASIS. Their
            // complete published endpoint must also be the actual joining cut.
            var cap=MembershipSourcePacket.included(envelope,basis,MembershipPeerRetentionSource.wrapper(peer)).value();
            require(cap.get("catalog").equals(current.terminal().catalog()) && cap.get("application").equals(current.terminal().application()),
                    "joining retention original source endpoint");
            peer.state().plan().capture(current,ancestry);learner.state().plan().required(current,ancestry);
            peers.add(peer.state().plan());learners.add(learner.state().plan());
        }
        var peerPlan=MembershipPeerRetentionPlan.mergeRecorded(context.root,context.view,peers);
        var learnerPlan=MembershipLearnerRetentionPlan.mergeRecorded(context.root,learners);
        peerPlan.required(current,ancestry);learnerPlan.required(current,ancestry);
        return new MembershipJoiningRetentionSeed(bytes,peerPlan,learnerPlan);
    }
    private static String base(byte[] bytes){return Base64.getEncoder().encodeToString(bytes);}
    private static byte[] unbase(Object value,int maximum) {
        require(value instanceof String && ((String)value).length()<=4L*((maximum+2L)/3),"joining retention member capacity");
        byte[] bytes=Base64.getDecoder().decode((String)value);
        require(bytes.length<=maximum && value.equals(base(bytes)),"joining retention canonical member");return bytes;
    }
}
