package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Publication-selector recovery intent. Its exact pre-publication revision makes
 * completion idempotent without undoing later actual-copy observations. */
final class MembershipFutureRetentionCompletion {
    static final int MAGIC=0x47534643,MAXIMUM=HEADER+32+4+MembershipPeerRetentionFiles.MAXIMUM;
    private final byte[] bytes;
    final MembershipSelectedRetention selected;
    final MembershipPeerRetentionPlan plan;
    private final MembershipPeerRetentionFiles.State before,after;
    private MembershipFutureRetentionCompletion(byte[] bytes,byte[] original,MembershipSelectedRetention selected,
            MembershipCapsule capsule,byte[] ancestry,MembershipIdentity owner) {
        this.bytes=bytes.clone();this.selected=selected;
        before=MembershipPeerRetentionFiles.decodeOwned(original,capsule.context.root,owner);
        require(!selected.needsCompletion(before),"future completion requires original selected merge");
        var next=before.plan();
        capsule.verifyAncestry(ancestry,selected.requiredParents());
        for(var proof:selected.futures())for(var peer:proof.state().peers)
            next=next.recordCoveredDispatch(capsule,ancestry,peer.identity(),peer.lower(),proof.state().target());
        plan=next;
        byte[] expected=Arrays.equals(plan.bytes(),before.plan().bytes())?original:
                MembershipPeerRetentionFiles.successor(original,capsule.context.root,owner,plan);
        after=MembershipPeerRetentionFiles.decodeOwned(expected,capsule.context.root,owner);
    }
    byte[] bytes(){return bytes.clone();}
    Map<String,byte[]> objects(){var result=selected.sourceObjects();result.put(hash(selected.bytes()),selected.bytes());result.put(hash(bytes),bytes());return result;}
    boolean needsCompletion(MembershipPeerRetentionFiles.State active) {
        require(active.revision()>=before.revision(),"future completion revision rollback");
        if(active.revision()==after.revision()) {require(active.digest().equals(after.digest()),"future completion changed expected ledger");return false;}
        if(active.revision()>after.revision())return false;
        require(active.revision()==before.revision() && active.digest().equals(before.digest()),"future completion changed original ledger");return true;
    }
    static MembershipFutureRetentionCompletion create(MembershipSelectedRetention selected,byte[] before,
            MembershipCapsule capsule,byte[] ancestry,MembershipIdentity owner) {
        require(!selected.futures().isEmpty(),"future completion empty intent");
        byte[] body=ByteBuffer.allocate(36+before.length).put(HexFormat.of().parseHex(hash(selected.bytes()))).putInt(before.length).put(before).array();
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(0).putInt(body.length).array();
        return new MembershipFutureRetentionCompletion(ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array(),before,selected,capsule,ancestry,owner);
    }
    static Optional<MembershipFutureRetentionCompletion> find(MembershipCapsule capsule,Decoded selection,MembershipIdentity owner,byte[] ancestry) {
        var selected=selection==null?Optional.<MembershipSelectedRetention>empty():MembershipSelectedRetention.find(capsule,selection,owner);MembershipFutureRetentionCompletion found=null;
        for(String h:capsule.packet.objectNames()) {
            int n=capsule.packet.objectSize(h);if(n<HEADER || n>MAXIMUM)continue;
            byte[] bytes=capsule.packet.objectBytes(h);if(ByteBuffer.wrap(bytes).getInt()!=MAGIC)continue;
            // Only a complete checksummed descriptor is a typed auxiliary object.
            var b=ByteBuffer.wrap(bytes);b.getInt();
            if(b.getShort()!=1 || b.getShort()!=3 || b.getInt()!=0 || b.getInt()!=n-HEADER)continue;
            byte[] body=Arrays.copyOfRange(bytes,HEADER,n);
            if(!Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),body)))continue;
            require(body.length>36,"future completion extent");b.position(HEADER);byte[] ref=new byte[32];b.get(ref);
            String reference=HexFormat.of().formatHex(ref);
            var retained=selection==null?MembershipSelectedRetention.referenced(capsule,reference,owner):selected;
            if(retained.isEmpty() || !hash(retained.get().bytes()).equals(reference))continue;
            int length=b.getInt();require(length>0 && length<=MembershipPeerRetentionFiles.MAXIMUM && length==b.remaining(),"future completion ledger extent");
            byte[] before=new byte[length];b.get(before);require(found==null,"duplicate future completion");
            found=create(retained.get(),before,capsule,ancestry,owner);
            require(Arrays.equals(bytes,found.bytes),"future completion noncanonical bytes");
        }
        return Optional.ofNullable(found);
    }
}
