package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Selector-bound learner merge. Keeps exact included force-bound source
 * snapshots and the original local revision before using confirmed progress. */
final class MembershipSelectedLearnerRetention {
    static final class Originals {
        final List<MembershipLearnerRetentionPlan> plans;
        final MembershipContext authority;
        private Originals(List<MembershipLearnerRetentionPlan> plans,MembershipContext authority) {
            this.plans=List.copyOf(plans);this.authority=authority;
        }
    }
    static final int MAGIC=0x47534c53;
    static final int MAXIMUM=HEADER+4+4096+4+65536+4+MembershipLearnerRetentionFiles.MAXIMUM+4
            +6*(12+16384+MembershipSourcePacket.ENVELOPE+MembershipLearnerRetentionSource.MAXIMUM);
    private record Row(Decoded basis,byte[] envelope,byte[] snapshot) {}
    private record Raw(MembershipIdentity owner,Decoded selected,byte[] before,List<Row> rows) {}
    private final byte[] bytes,after;
    final MembershipLearnerRetentionPlan plan;
    private final MembershipLearnerRetentionFiles.State initial,expected;
    private MembershipSelectedLearnerRetention(byte[] bytes,Raw raw,MembershipLearnerRetentionPlan plan) {
        this.bytes=bytes.clone();this.plan=plan;String root=(String)raw.selected.value().get("root");
        initial=MembershipLearnerRetentionFiles.decodeOwned(raw.before,root,raw.owner);
        after=Arrays.equals(initial.plan().bytes(),plan.bytes())?raw.before.clone():MembershipLearnerRetentionFiles.successor(raw.before,root,raw.owner,plan);
        expected=MembershipLearnerRetentionFiles.decodeOwned(after,root,raw.owner);
    }
    byte[] bytes(){return bytes.clone();}
    long completionBytes(){return initial.revision()==expected.revision()?0:after.length;}
    boolean needsCompletion(MembershipLearnerRetentionFiles.State active) {
        require(active.revision()>=initial.revision(),"selected learner revision rollback");
        if(active.revision()==expected.revision()) {
            require(active.digest().equals(expected.digest()),"selected learner completed bytes changed");return false;
        }
        if(active.revision()>expected.revision())return false;
        require(active.revision()==initial.revision() && active.digest().equals(initial.digest()),"selected learner original ledger changed");return true;
    }
    static MembershipSelectedLearnerRetention capture(MembershipSelection.Decision decision,MembershipIdentity local,byte[] before) {
        var rows=new ArrayList<Row>();
        for(var source:decision.sources()) {
            var frozen=MembershipLearnerRetentionSource.read(source);
            rows.add(new Row(source.basis,source.capsule.packet.envelope(),MembershipLearnerRetentionSource.wrapper(frozen)));
        }
        var raw=new Raw(local,decision.selected(),before.clone(),List.copyOf(rows));
        return verify(encode(raw),raw,decision.selected(),local,decision.longest().capsule);
    }
    static Optional<MembershipSelectedLearnerRetention> find(MembershipCapsule capsule,Decoded selected,MembershipIdentity local) {
        MembershipSelectedLearnerRetention found=null;
        for(String h:capsule.packet.objectNames()) {
            int n=capsule.packet.objectSize(h);if(n<HEADER || n>MAXIMUM)continue;
            byte[] bytes=capsule.packet.objectBytes(h);if(ByteBuffer.wrap(bytes).getInt()!=MAGIC)continue;
            Raw raw;try{raw=parse(bytes);}catch(IllegalArgumentException invalid){continue;}
            if(!raw.owner.equals(local) || !raw.selected.digest().equals(selected.digest()))continue;
            require(found==null,"duplicate selected learner intent");found=verify(bytes,raw,selected,local,capsule);
        }
        return Optional.ofNullable(found);
    }
    private static MembershipSelectedLearnerRetention verify(byte[] bytes,Raw raw,Decoded selected,MembershipIdentity local,MembershipCapsule authority) {
        require(raw.owner.equals(local) && Arrays.equals(raw.selected.bytes(),selected.bytes()),"selected learner identity/selection");
        String root=(String)selected.value().get("root");
        require(root.equals(authority.context.root) && local.equals(authority.context.identities.get(local.nodeId().value())),"selected learner original root/owner");
        var refs=list(selected.value().get("sources"));require(raw.rows.size()==refs.size(),"selected learner source count");
        var bases=new ByteArrayOutputStream();var plans=new ArrayList<MembershipLearnerRetentionPlan>();
        plans.add(MembershipLearnerRetentionFiles.decodeOwned(raw.before,root,local).plan());
        for(int i=0;i<raw.rows.size();i++) {
            var row=raw.rows.get(i);var ref=object(refs.get(i));var owner=authority.context.identities.get((String)ref.get("voter"));
            require(owner!=null,"selected learner permanent source missing");
            plans.add(MembershipLearnerRetentionSource.included(row.envelope,row.basis,owner,row.snapshot).state().plan());bases.writeBytes(row.basis.bytes());
        }
        MembershipSelectedSources.cuts(bases.toByteArray(),selected);
        require(refs.stream().map(MembershipFormat::object).anyMatch(r->r.get("voter").equals(local.nodeId().value())),"selected learner local source missing");
        return new MembershipSelectedLearnerRetention(bytes,raw,MembershipLearnerRetentionPlan.mergeSelected(root,new Originals(plans,authority.context)));
    }
    private static void part(ByteArrayOutputStream output,byte[] bytes,int maximum) {
        require(bytes.length>0 && bytes.length<=maximum,"selected learner member bound");
        output.writeBytes(ByteBuffer.allocate(4).putInt(bytes.length).array());output.writeBytes(bytes);
    }
    private static byte[] encode(Raw raw) {
        require(raw.rows.size()>=2 && raw.rows.size()<=6,"selected learner rows");var body=new ByteArrayOutputStream();
        part(body,canonical(MembershipPeerRetentionPlan.identity(raw.owner),4096),4096);part(body,raw.selected.bytes(),65536);
        part(body,raw.before,MembershipLearnerRetentionFiles.MAXIMUM);body.writeBytes(ByteBuffer.allocate(4).putInt(raw.rows.size()).array());
        for(var row:raw.rows){part(body,row.basis.bytes(),16384);part(body,row.envelope,MembershipSourcePacket.ENVELOPE);part(body,row.snapshot,MembershipLearnerRetentionSource.MAXIMUM);}
        byte[] content=body.toByteArray();require(HEADER+content.length<=MAXIMUM && MAXIMUM<=FRAME,"selected learner total bound");
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(0).putInt(content.length).array();
        return ByteBuffer.allocate(HEADER+content.length).put(prefix).put(sha(prefix,content)).put(content).array();
    }
    private static byte[] part(ByteBuffer input,int maximum) {
        require(input.remaining()>=4,"selected learner missing length");int n=input.getInt();
        require(n>0 && n<=maximum && n<=input.remaining(),"selected learner member extent");byte[] bytes=new byte[n];input.get(bytes);return bytes;
    }
    private static Raw parse(byte[] bytes) {
        require(bytes.length>HEADER && bytes.length<=MAXIMUM,"selected learner extent");var input=ByteBuffer.wrap(bytes);
        require(input.getInt()==MAGIC && input.getShort()==1 && input.getShort()==3 && input.getInt()==0 && input.getInt()==bytes.length-HEADER,"selected learner header");
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,HEADER,bytes.length))),"selected learner checksum");
        input.position(HEADER);var owner=MembershipContext.identity(object(MembershipFormat.parse(part(input,4096),4096)));
        var selected=decode(part(input,65536),"records","SELECTED");byte[] before=part(input,MembershipLearnerRetentionFiles.MAXIMUM);
        require(input.remaining()>=4,"selected learner missing count");int count=input.getInt();require(count>=2 && count<=6,"selected learner count");
        var rows=new ArrayList<Row>();for(int i=0;i<count;i++)rows.add(new Row(decode(part(input,16384),"records","BASIS"),part(input,MembershipSourcePacket.ENVELOPE),part(input,MembershipLearnerRetentionSource.MAXIMUM)));
        require(!input.hasRemaining(),"selected learner trailing bytes");var raw=new Raw(owner,selected,before,List.copyOf(rows));
        require(Arrays.equals(bytes,encode(raw)),"selected learner canonical bytes");return raw;
    }
}
