package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Local selector-coupled merge intent. Exact included originals are retained, not
 * six full source packets. This is not permission to dispatch or a new vote. */
final class MembershipSelectedRetention {
    static final int MAGIC=0x47535253;
    static final int MAXIMUM=HEADER+4+4096+4+65536+4+MembershipPeerRetentionFiles.MAXIMUM+4
            +6*(12+16384+MembershipSourcePacket.ENVELOPE+MembershipPeerRetentionSource.MAXIMUM);
    private record Row(Decoded basis,byte[] envelope,byte[] snapshot) {}
    private record Raw(MembershipIdentity owner,Decoded selected,byte[] before,List<Row> rows) {}
    private final byte[] bytes,before,after;
    final MembershipPeerRetentionPlan plan;
    private final MembershipPeerRetentionFiles.State initial,expected;
    private MembershipSelectedRetention(byte[] bytes,Raw raw,MembershipPeerRetentionPlan plan) {
        this.bytes=bytes.clone();before=raw.before.clone();this.plan=plan;
        String root=(String)raw.selected.value().get("root");initial=MembershipPeerRetentionFiles.decodeOwned(before,root,raw.owner);
        after=Arrays.equals(initial.plan().bytes(),plan.bytes())?before.clone():MembershipPeerRetentionFiles.successor(before,root,raw.owner,plan);
        expected=MembershipPeerRetentionFiles.decodeOwned(after,root,raw.owner);
    }
    byte[] bytes(){return bytes.clone();}
    long completionBytes(){return expected.revision()==initial.revision()?0:after.length;}
    /** Later native revisions have already passed this exact merge. Do not restore
     * stale uncertainty after a real observation narrowed a subsequent revision. */
    boolean needsCompletion(MembershipPeerRetentionFiles.State active) {
        require(active.revision()>=initial.revision(),"selected retention local revision rollback");
        if(active.revision()==expected.revision()) {
            require(active.digest().equals(expected.digest()),"selected retention completed bytes changed");return false;
        }
        if(active.revision()>expected.revision())return false;
        require(active.revision()==initial.revision() && active.digest().equals(initial.digest()),"selected retention original ledger changed");
        return true;
    }
    static MembershipSelectedRetention capture(MembershipSelection.Decision decision,MembershipIdentity local,byte[] before) {
        var rows=new ArrayList<Row>();
        for(var source:decision.sources()) {
            var frozen=MembershipPeerRetentionSource.read(source);
            require(frozen.future()==null,"selected future retention propagation required");
            rows.add(new Row(source.basis,source.capsule.packet.envelope(),MembershipPeerRetentionSource.wrapper(frozen)));
        }
        var raw=new Raw(local,decision.selected(),before.clone(),List.copyOf(rows));
        return verify(encode(raw),raw,decision.selected(),local,decision.longest().capsule);
    }
    static Optional<MembershipSelectedRetention> find(MembershipCapsule capsule,Decoded selected,MembershipIdentity local) {
        MembershipSelectedRetention found=null;
        for(String h:capsule.packet.objectNames()) {
            int size=capsule.packet.objectSize(h);if(size<HEADER || size>MAXIMUM)continue;
            byte[] bytes=capsule.packet.objectBytes(h);if(ByteBuffer.wrap(bytes).getInt()!=MAGIC)continue;
            Raw raw;try{raw=parse(bytes);}catch(IllegalArgumentException invalid){continue;}
            if(!raw.owner.equals(local) || !raw.selected.digest().equals(selected.digest()))continue;
            require(found==null,"duplicate selected retention intent");found=verify(bytes,raw,selected,local,capsule);
        }
        return Optional.ofNullable(found);
    }
    private static MembershipSelectedRetention verify(byte[] bytes,Raw raw,Decoded selected,MembershipIdentity local,MembershipCapsule authority) {
        require(raw.owner.equals(local) && Arrays.equals(raw.selected.bytes(),selected.bytes()),"selected retention identity/selection");
        var value=selected.value();String root=(String)value.get("root");var view=object(object(value.get("cut")).get("view"));
        require(root.equals(authority.context.root) && local.equals(authority.context.identities.get(local.nodeId().value())),"selected retention original root/owner");
        var refs=list(value.get("sources"));require(raw.rows.size()==refs.size(),"selected retention source count");
        var bases=new ByteArrayOutputStream();var plans=new ArrayList<MembershipPeerRetentionPlan>();
        plans.add(MembershipPeerRetentionFiles.decodeOwned(raw.before,root,local).plan());
        for(int i=0;i<raw.rows.size();i++) {
            var row=raw.rows.get(i);var ref=object(refs.get(i));
            var owner=authority.context.identities.get((String)ref.get("voter"));require(owner!=null,"selected retention permanent source absent");
            var frozen=MembershipPeerRetentionSource.included(row.envelope,row.basis,owner,row.snapshot);
            plans.add(frozen.state().plan());bases.writeBytes(row.basis.bytes());
        }
        MembershipSelectedSources.cuts(bases.toByteArray(),selected);
        require(refs.stream().map(MembershipFormat::object).anyMatch(r->r.get("voter").equals(local.nodeId().value())),"selected retention local source absent");
        return new MembershipSelectedRetention(bytes,raw,MembershipPeerRetentionPlan.mergeRecorded(root,view,plans));
    }
    private static void part(ByteArrayOutputStream output,byte[] bytes,int maximum) {
        require(bytes.length>0 && bytes.length<=maximum,"selected retention member bound");
        output.writeBytes(ByteBuffer.allocate(4).putInt(bytes.length).array());output.writeBytes(bytes);
    }
    private static byte[] encode(Raw raw) {
        require(raw.rows.size()>=2 && raw.rows.size()<=6,"selected retention rows");var body=new ByteArrayOutputStream();
        part(body,canonical(MembershipPeerRetentionPlan.identity(raw.owner),4096),4096);part(body,raw.selected.bytes(),65536);
        part(body,raw.before,MembershipPeerRetentionFiles.MAXIMUM);body.writeBytes(ByteBuffer.allocate(4).putInt(raw.rows.size()).array());
        for(var row:raw.rows){part(body,row.basis.bytes(),16384);part(body,row.envelope,MembershipSourcePacket.ENVELOPE);part(body,row.snapshot,MembershipPeerRetentionSource.MAXIMUM);}
        byte[] content=body.toByteArray();require(HEADER+content.length<=MAXIMUM && MAXIMUM<=FRAME,"selected retention total bound");
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(0).putInt(content.length).array();
        return ByteBuffer.allocate(HEADER+content.length).put(prefix).put(sha(prefix,content)).put(content).array();
    }
    private static byte[] part(ByteBuffer input,int maximum) {
        require(input.remaining()>=4,"selected retention missing length");int n=input.getInt();
        require(n>0 && n<=maximum && n<=input.remaining(),"selected retention member extent");byte[] bytes=new byte[n];input.get(bytes);return bytes;
    }
    private static Raw parse(byte[] bytes) {
        require(bytes.length>HEADER && bytes.length<=MAXIMUM,"selected retention extent");var input=ByteBuffer.wrap(bytes);
        require(input.getInt()==MAGIC && input.getShort()==1 && input.getShort()==3 && input.getInt()==0 && input.getInt()==bytes.length-HEADER,"selected retention header");
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,HEADER,bytes.length))),"selected retention checksum");
        input.position(HEADER);var identity=MembershipContext.identity(object(MembershipFormat.parse(part(input,4096),4096)));
        var selected=decode(part(input,65536),"records","SELECTED");byte[] before=part(input,MembershipPeerRetentionFiles.MAXIMUM);
        require(input.remaining()>=4,"selected retention missing count");int n=input.getInt();require(n>=2 && n<=6,"selected retention count");
        var rows=new ArrayList<Row>();
        for(int i=0;i<n;i++)rows.add(new Row(decode(part(input,16384),"records","BASIS"),part(input,MembershipSourcePacket.ENVELOPE),part(input,MembershipPeerRetentionSource.MAXIMUM)));
        require(!input.hasRemaining(),"selected retention trailing bytes");var raw=new Raw(identity,selected,before,List.copyOf(rows));
        require(Arrays.equals(bytes,encode(raw)),"selected retention canonical bytes");return raw;
    }
}
