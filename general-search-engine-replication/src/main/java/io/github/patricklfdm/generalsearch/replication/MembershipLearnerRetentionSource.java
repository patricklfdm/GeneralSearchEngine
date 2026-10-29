package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact nonvoting obligation committed by a frozen BASIS inventory. Inclusion
 * proves only which bytes that source froze, never a learner ACK/export permit. */
final class MembershipLearnerRetentionSource {
    static final int MAGIC=0x47534c46,MAXIMUM=HEADER+8+8192+MembershipLearnerRetentionFiles.MAXIMUM;
    record Frozen(Decoded promise,byte[] localBytes,MembershipLearnerRetentionFiles.State state) {
        Frozen {localBytes=localBytes.clone();}
        @Override public byte[] localBytes(){return localBytes.clone();}
    }
    private record Raw(Decoded promise,byte[] state) {}
    static byte[] wrapper(Frozen frozen){return encode(frozen.promise,frozen.localBytes);}
    private static byte[] encode(Decoded promise,byte[] state) {
        require(promise.family().equals("records") && promise.kind().equals("PROMISE") && promise.value().get("basisId")!=null,
                "learner source capture promise");
        byte[] p=promise.bytes();require(p.length<=8192 && state.length<=MembershipLearnerRetentionFiles.MAXIMUM,"learner source bounds");
        byte[] body=ByteBuffer.allocate(8+p.length+state.length).putInt(p.length).put(p).putInt(state.length).put(state).array();
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(0).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    private static Raw decode(byte[] bytes) {
        require(bytes.length>HEADER+8 && bytes.length<=MAXIMUM,"learner source extent");var b=ByteBuffer.wrap(bytes);
        require(b.getInt()==MAGIC && b.getShort()==1 && b.getShort()==3 && b.getInt()==0 && b.getInt()==bytes.length-HEADER,"learner source framing");
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,HEADER,bytes.length))),"learner source checksum");
        b.position(HEADER);int n=b.getInt();require(n>=HEADER && n<=8192 && n<=b.remaining()-4,"learner source promise extent");
        byte[] p=new byte[n];b.get(p);var promise=MembershipFormat.decode(p,"records","PROMISE");
        n=b.getInt();require(n>MembershipLearnerRetentionFiles.HEADER && n<=MembershipLearnerRetentionFiles.MAXIMUM && n==b.remaining(),"learner source state extent");
        byte[] state=new byte[n];b.get(state);require(Arrays.equals(bytes,encode(promise,state)),"learner source noncanonical bytes");return new Raw(promise,state);
    }
    static MembershipSourcePacket freeze(MembershipSourcePacket original,Decoded promise,MembershipIdentity owner,byte[] local) {
        MembershipLearnerRetentionFiles.decodeOwned(local,(String)original.capsule().value().get("root"),owner);
        require(promise.value().get("root").equals(original.capsule().value().get("root")),"learner source foreign promise");
        var objects=new TreeMap<String,byte[]>();for(String h:original.objectNames())objects.put(h,original.objectBytes(h));
        byte[] captured=encode(promise,local);objects.put(hash(captured),captured);
        var cap=new TreeMap<>(original.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(MembershipFormat.decode(MembershipFormat.encode("records","CAPSULE",cap),"records","CAPSULE"),objects,original.images()));
    }
    private static Optional<Raw> find(MembershipSourcePacket packet,Decoded basis) {
        packet.bind(basis);Raw found=null;
        for(String h:packet.objectNames()) {
            int size=packet.objectSize(h);if(size<4 || size>MAXIMUM)continue;
            byte[] bytes=packet.objectBytes(h);if(ByteBuffer.wrap(bytes).getInt()!=MAGIC)continue;
            Raw candidate;try{candidate=decode(bytes);}catch(IllegalArgumentException invalid){continue;}
            if(!Objects.equals(candidate.promise.value().get("basisId"),basis.value().get("basisId")))continue;
            for(String field:List.of("root","view","ballot","basisId"))
                require(candidate.promise.value().get(field).equals(basis.value().get(field)),"learner source promise binding");
            require(found==null,"learner source duplicate original state");found=candidate;
        }
        return Optional.ofNullable(found);
    }
    static Frozen read(MembershipSelection.Source source) {
        var raw=find(source.capsule.packet,source.basis).orElseThrow(()->new IllegalArgumentException("learner source original snapshot missing"));
        return included(source.capsule.packet.envelope(),source.basis,source.owner,encode(raw.promise,raw.state));
    }
    static Frozen included(byte[] envelope,Decoded basis,MembershipIdentity owner,byte[] wrapper) {
        var cap=MembershipSourcePacket.included(envelope,basis,wrapper);var raw=decode(wrapper);
        for(String field:List.of("root","view","ballot","basisId"))
            require(raw.promise.value().get(field).equals(basis.value().get(field)),"included learner source promise binding");
        require(basis.value().get("voter").equals(owner.nodeId().value()),"included learner source owner");
        return new Frozen(raw.promise,raw.state,MembershipLearnerRetentionFiles.decodeOwned(raw.state,(String)cap.value().get("root"),owner));
    }
    /** A legacy owner cannot select sources whose obligation it would discard. */
    static void requireLegacyCompatible(MembershipSelection.Source source) {
        require(find(source.capsule.packet,source.basis).isEmpty(),"selected learner retention propagation required");
    }
    private MembershipLearnerRetentionSource() {}
}
