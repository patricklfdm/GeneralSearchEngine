package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import java.util.function.Function;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Flat inherited obligations. Original GSFT owners are never relabelled as the
 * capturing owner, and copied proofs do not create any new voting observations. */
final class MembershipFutureRetentionSet {
    static final int MAGIC=0x47534653,MAXIMUM=32768;
    record Proof(byte[] bytes,MembershipFutureRetentionFiles.State state) {
        Proof { bytes=bytes.clone(); }
        @Override public byte[] bytes(){return bytes.clone();}
    }
    static byte[] encode(String root,MembershipIdentity owner,Collection<Proof> proofs) {
        MembershipValidation.digest(root);var ordered=new TreeMap<String,Proof>();
        for(var proof:proofs)ordered.put(hash(proof.bytes),proof);
        require(!ordered.isEmpty() && ordered.size()<=6,"inherited future proof capacity");
        var refs=new ArrayList<Map<String,Object>>();
        for(var row:ordered.entrySet()) {
            var proof=row.getValue();
            require(hash(proof.bytes).equals(proof.state.digest),"inherited future original state digest");
            MembershipFutureRetentionFiles.decodeOwned(proof.bytes,root,proof.state.owner);
            require(proof.state.pending() && proof.state.root.equals(root),"inherited future root/state");
            refs.add(Map.of("owner",MembershipPeerRetentionPlan.identity(proof.state.owner),"sha256",row.getKey()));
        }
        byte[] body=canonical(Map.of("root",root,"owner",MembershipPeerRetentionPlan.identity(owner),"proofs",refs),MAXIMUM-HEADER);
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(0).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    static List<Proof> decode(byte[] bytes,String root,MembershipIdentity owner,Function<String,byte[]> reader) {
        require(bytes!=null && bytes.length>HEADER && bytes.length<=MAXIMUM,"inherited future extent");var b=ByteBuffer.wrap(bytes);
        require(b.getInt()==MAGIC && b.getShort()==1 && b.getShort()==3 && b.getInt()==0 && b.getInt()==bytes.length-HEADER,"inherited future framing");
        byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),body)),"inherited future checksum");
        var value=object(parse(body,MAXIMUM-HEADER));
        require(value.keySet().equals(Set.of("root","owner","proofs")) && root.equals(value.get("root"))
                && value.get("owner").equals(MembershipPeerRetentionPlan.identity(owner)),"inherited future capture identity");
        var rows=list(value.get("proofs"));require(!rows.isEmpty() && rows.size()<=6,"inherited future proof count");
        var proofs=new ArrayList<Proof>();String previous="";
        for(var item:rows) {
            var row=object(item);require(row.keySet().equals(Set.of("owner","sha256")),"inherited future reference fields");
            String digest=(String)row.get("sha256");MembershipValidation.digest(digest);
            require(digest.compareTo(previous)>0,"inherited future reference order");previous=digest;
            byte[] proof=reader.apply(digest);
            require(proof!=null && proof.length<=MembershipFutureRetentionFiles.MAXIMUM && hash(proof).equals(digest),"inherited future original missing/digest");
            var originalOwner=MembershipContext.identity(object(row.get("owner")));
            var state=MembershipFutureRetentionFiles.decodeOwned(proof,root,originalOwner);
            require(state.pending(),"inherited future empty original");proofs.add(new Proof(proof,state));
        }
        require(Arrays.equals(bytes,encode(root,owner,proofs)),"inherited future canonical bytes");return List.copyOf(proofs);
    }
    private MembershipFutureRetentionSet() {}
}
