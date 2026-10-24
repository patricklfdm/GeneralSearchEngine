package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.compareBallot;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** A higher selected ACCEPT is not a replacement for the owner's original vote.
 * The already reconstructed context and every original byte remain required. */
final class MembershipContextTail {
    private static boolean sameSlot(Decoded left,Decoded right) {
        var a=new TreeMap<>(left.value());var b=new TreeMap<>(right.value());a.remove("ballot");b.remove("ballot");return a.equals(b);
    }
    static Decoded selected(MembershipPendingContext.Reconstructed original,MembershipSourcePacket packet,String tail) {
        require(tail!=null,"context selected tail missing");var selected=decode(packet.objectBytes(tail),"records","ACCEPT");var vote=original.vote();
        require(sameSlot(selected,vote.accept()) && compareBallot(object(selected.value().get("ballot")),object(vote.accept().value().get("ballot")))>=0,
                "context selected tail changes original slot or regresses ballot");
        for(byte[] bytes:List.of(vote.accept().bytes(),vote.entry().bytes(),vote.payload()))
            require(Arrays.equals(bytes,packet.objectBytes(hash(bytes))),"context selected tail loses exact original bytes");
        return selected;
    }
    static boolean retained(MembershipCurrentGeneration current,Decoded obsolete,MembershipPendingContext.Reconstructed original) {
        if(original==null)return false;
        require(current.capsule.terminal().equals(original.capsule().terminal()),"context tail retirement changes original parent");
        var selected=selected(original,current.capsule.packet,current.accepted);
        return sameSlot(selected,obsolete) && compareBallot(object(selected.value().get("ballot")),object(obsolete.value().get("ballot")))>=0
                && Arrays.equals(obsolete.bytes(),current.capsule.packet.objectBytes(obsolete.digest()));
    }
    /** Read-only completion admission may inspect a proposed vote. Deletion callers
     * must supply the exact already forced, checked current vote under their owner. */
    static boolean successor(MembershipCurrentGeneration current,Decoded obsolete,MembershipPendingAccept.Vote vote) {
        if(vote==null || current.accepted==null)return false;
        var selected=current.capsule.context.record(current.accepted,"ACCEPT");
        return Arrays.equals(vote.selector().bytes(),current.selector.bytes())
                && vote.promise().digest().equals(current.manifest.value().get("promise"))
                && vote.selected().digest().equals(current.manifest.value().get("selection"))
                && sameSlot(selected,obsolete) && sameSlot(selected,vote.accept())
                && compareBallot(object(selected.value().get("ballot")),object(obsolete.value().get("ballot")))>=0
                && compareBallot(object(vote.accept().value().get("ballot")),object(selected.value().get("ballot")))>=0
                && Arrays.equals(obsolete.bytes(),current.capsule.packet.objectBytes(obsolete.digest()));
    }
    private MembershipContextTail() {}
}
