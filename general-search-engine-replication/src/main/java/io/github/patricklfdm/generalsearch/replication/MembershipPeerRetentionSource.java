package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact pre-PROMISE local retention snapshot inside the immutable source index.
 * This authenticates which local bytes were frozen, not a quorum intent, a peer
 * progress observation, or permission to discard any other selected obligation. */
final class MembershipPeerRetentionSource {
    static final int MAGIC=0x47535250,MAXIMUM=HEADER+8+8192+MembershipPeerRetentionFiles.MAXIMUM;
    record Frozen(Decoded promise,byte[] localBytes,MembershipPeerRetentionFiles.State state) {
        Frozen {localBytes=localBytes.clone();}
        @Override public byte[] localBytes(){return localBytes.clone();}
    }
    private record Raw(Decoded promise,byte[] state) {}
    private static byte[] encode(Decoded promise,byte[] localBytes) {
        require(promise.family().equals("records") && promise.kind().equals("PROMISE")
                && promise.value().get("basisId")!=null,"retention source requires capture promise");
        byte[] p=promise.bytes();require(p.length<=8192 && localBytes.length<=MembershipPeerRetentionFiles.MAXIMUM,"retention source bounds");
        byte[] body=ByteBuffer.allocate(8+p.length+localBytes.length).putInt(p.length).put(p).putInt(localBytes.length).put(localBytes).array();
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(0).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    private static Raw decode(byte[] bytes) {
        require(bytes.length>HEADER+8 && bytes.length<=MAXIMUM,"retention source extent");var b=ByteBuffer.wrap(bytes);
        require(b.getInt()==MAGIC && b.getShort()==1 && b.getShort()==3 && b.getInt()==0 && b.getInt()==bytes.length-HEADER,"retention source framing");
        byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),body)),"retention source checksum");
        b.position(HEADER);int n=b.getInt();require(n>=HEADER && n<=8192 && n<=b.remaining()-4,"retention source promise extent");
        byte[] p=new byte[n];b.get(p);var promise=MembershipFormat.decode(p,"records","PROMISE");
        n=b.getInt();require(n>MembershipPeerRetentionFiles.HEADER && n<=MembershipPeerRetentionFiles.MAXIMUM && n==b.remaining(),"retention source state extent");
        byte[] state=new byte[n];b.get(state);require(Arrays.equals(bytes,encode(promise,state)),"retention source noncanonical bytes");return new Raw(promise,state);
    }
    static MembershipSourcePacket freeze(MembershipSourcePacket original,Decoded promise,MembershipIdentity owner,byte[] localBytes) {
        MembershipPeerRetentionFiles.decodeOwned(localBytes,(String)original.capsule().value().get("root"),owner);
        require(promise.value().get("root").equals(original.capsule().value().get("root")),"retention source foreign promise");
        var objects=new TreeMap<String,byte[]>();
        for(String key:original.objectNames())objects.put(key,original.objectBytes(key));
        // Do not erase an older indexed object: pending-context envelopes can still
        // require its exact original bytes. Ordinary certified compaction prunes extras.
        byte[] captured=encode(promise,localBytes);objects.put(hash(captured),captured);
        var cap=new TreeMap<>(original.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(MembershipFormat.decode(MembershipFormat.encode("records","CAPSULE",cap),"records","CAPSULE"),objects,original.images()));
    }
    static Frozen read(MembershipSelection.Source source) {
        var expected=source.basis.value();Raw found=null;
        // The complete packet is already bounded. No optional hint or live mutable
        // state can substitute for the exact object committed by this BASIS index.
        for(String key:source.capsule.packet.objectNames()) {
            int n=source.capsule.packet.objectSize(key);if(n<4 || n>MAXIMUM)continue;
            byte[] bytes=source.capsule.packet.objectBytes(key);if(ByteBuffer.wrap(bytes).getInt()!=MAGIC)continue;
            Raw candidate;
            // Packet objects also include arbitrary DATA payloads. A coincidental
            // magic prefix is not a type declaration; only a complete canonical
            // wrapper can be considered, and one exact capture is still required.
            try{candidate=decode(bytes);}catch(IllegalArgumentException invalid){continue;}
            var value=candidate.promise.value();
            if(!Objects.equals(value.get("basisId"),expected.get("basisId")))continue;
            for(String field:List.of("root","view","ballot","basisId"))require(value.get(field).equals(expected.get(field)),"retention source original promise binding");
            require(found==null,"retention source duplicate original state");found=candidate;
        }
        require(found!=null,"retention source original snapshot missing");
        var state=MembershipPeerRetentionFiles.decodeOwned(found.state,source.capsule.context.root,source.owner);
        return new Frozen(found.promise,found.state,state);
    }
    private MembershipPeerRetentionSource() {}
}
