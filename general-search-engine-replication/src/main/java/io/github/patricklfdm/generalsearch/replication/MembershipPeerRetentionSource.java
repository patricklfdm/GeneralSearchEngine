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
    record Frozen(Decoded promise,byte[] localBytes,MembershipPeerRetentionFiles.State state,byte[] futureBytes,
            MembershipFutureRetentionFiles.State future) {
        Frozen {localBytes=localBytes.clone();futureBytes=futureBytes==null?null:futureBytes.clone();}
        @Override public byte[] localBytes(){return localBytes.clone();}
        @Override public byte[] futureBytes(){return futureBytes==null?null:futureBytes.clone();}
    }
    private record Raw(Decoded promise,byte[] state,String future) {}
    static byte[] wrapper(Frozen value){return encode(value.promise,value.localBytes,value.futureBytes==null?null:hash(value.futureBytes));}
    private static byte[] encode(Decoded promise,byte[] localBytes,String future) {
        require(promise.family().equals("records") && promise.kind().equals("PROMISE")
                && promise.value().get("basisId")!=null,"retention source requires capture promise");
        byte[] p=promise.bytes();require(p.length<=8192 && localBytes.length<=MembershipPeerRetentionFiles.MAXIMUM,"retention source bounds");
        var buffer=ByteBuffer.allocate(8+p.length+localBytes.length+(future==null?0:32)).putInt(p.length).put(p).putInt(localBytes.length).put(localBytes);
        if(future!=null){MembershipValidation.digest(future);buffer.put(HexFormat.of().parseHex(future));}
        byte[] body=buffer.array();require(HEADER+body.length<=MAXIMUM,"retention source total capacity");
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(future==null?0:1).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    private static Raw decode(byte[] bytes) {
        require(bytes.length>HEADER+8 && bytes.length<=MAXIMUM,"retention source extent");var b=ByteBuffer.wrap(bytes);
        require(b.getInt()==MAGIC && b.getShort()==1 && b.getShort()==3,"retention source framing");
        int flags=b.getInt();require((flags==0 || flags==1) && b.getInt()==bytes.length-HEADER,"retention source framing");
        byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),body)),"retention source checksum");
        b.position(HEADER);int n=b.getInt();require(n>=HEADER && n<=8192 && n<=b.remaining()-4,"retention source promise extent");
        byte[] p=new byte[n];b.get(p);var promise=MembershipFormat.decode(p,"records","PROMISE");
        n=b.getInt();require(n>MembershipPeerRetentionFiles.HEADER && n<=MembershipPeerRetentionFiles.MAXIMUM && n==b.remaining()-(flags==1?32:0),"retention source state extent");
        byte[] state=new byte[n];b.get(state);String future=null;
        if(flags==1){byte[] digest=new byte[32];b.get(digest);future=HexFormat.of().formatHex(digest);}
        require(Arrays.equals(bytes,encode(promise,state,future)),"retention source noncanonical bytes");return new Raw(promise,state,future);
    }
    static MembershipSourcePacket freeze(MembershipSourcePacket original,Decoded promise,MembershipIdentity owner,byte[] localBytes) {
        return freeze(original,promise,owner,localBytes,null);
    }
    static MembershipSourcePacket freeze(MembershipSourcePacket original,Decoded promise,MembershipIdentity owner,byte[] localBytes,byte[] futureBytes) {
        MembershipPeerRetentionFiles.decodeOwned(localBytes,(String)original.capsule().value().get("root"),owner);
        require(promise.value().get("root").equals(original.capsule().value().get("root")),"retention source foreign promise");
        if(futureBytes!=null)require(MembershipFutureRetentionFiles.decodeOwned(futureBytes,(String)promise.value().get("root"),owner).pending(),"retention source empty future reference");
        var objects=new TreeMap<String,byte[]>();
        for(String key:original.objectNames())objects.put(key,original.objectBytes(key));
        // Do not erase an older indexed object: pending-context envelopes can still
        // require its exact original bytes. Ordinary certified compaction prunes extras.
        // Original proof is a separately indexed object; six full catalogs must
        // never be embedded in the selected-ledger metadata. Existing bounds hold.
        if(futureBytes!=null)objects.put(hash(futureBytes),futureBytes.clone());
        byte[] captured=encode(promise,localBytes,futureBytes==null?null:hash(futureBytes));objects.put(hash(captured),captured);
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
        byte[] futureBytes=null;MembershipFutureRetentionFiles.State future=null;
        if(found.future!=null) {
            require(source.capsule.packet.objectNames().contains(found.future),"retention source future proof missing");
            require(source.capsule.packet.objectSize(found.future)<=MembershipFutureRetentionFiles.MAXIMUM,"retention source future proof extent");
            futureBytes=source.capsule.packet.objectBytes(found.future);
            future=MembershipFutureRetentionFiles.decodeOwned(futureBytes,source.capsule.context.root,source.owner);
            require(future.pending() && future.parent.equals(source.capsule.terminal()),"retention source future parent");
            require(source.accepted!=null && Arrays.equals(source.accepted.bytes(),future.record("accept.gsr").bytes())
                    && Arrays.equals(source.entry.bytes(),future.record("entry.gsr").bytes()),"retention source future original tail");
            for(var peer:future.peers)state.plan().possible(peer.identity());
            // This is the exact owned source's conservative obligation, not an
            // ancestry proof or a new peer application/installation observation.
        }
        return new Frozen(found.promise,found.state,state,futureBytes,future);
    }
    static Frozen included(byte[] envelope,Decoded basis,MembershipIdentity owner,byte[] wrapper) {
        var raw=decode(wrapper);
        require(raw.future==null,"selected future retention propagation required");
        return included(envelope,basis,owner,wrapper,null);
    }
    /** Exact separately indexed future proof. Inclusion is historical ownership,
     * never a new voter/application observation or permission to dispatch. */
    static Frozen included(byte[] envelope,Decoded basis,MembershipIdentity owner,byte[] wrapper,byte[] futureBytes) {
        var cap=MembershipSourcePacket.included(envelope,basis,wrapper);var raw=decode(wrapper);
        for(String field:List.of("root","view","ballot","basisId"))
            require(raw.promise.value().get(field).equals(basis.value().get(field)),"included retention original promise binding");
        require(basis.value().get("voter").equals(owner.nodeId().value()),"included retention source owner");
        var state=MembershipPeerRetentionFiles.decodeOwned(raw.state,(String)cap.value().get("root"),owner);
        require((raw.future==null)==(futureBytes==null),"included retention future presence");
        MembershipFutureRetentionFiles.State future=null;
        if(futureBytes!=null) {
            require(futureBytes.length<=MembershipFutureRetentionFiles.MAXIMUM && raw.future.equals(hash(futureBytes)),"included retention future digest/extent");
            MembershipSourcePacket.included(envelope,basis,futureBytes);
            future=MembershipFutureRetentionFiles.decodeOwned(futureBytes,(String)cap.value().get("root"),owner);
            var parent=new MembershipCapsule.Anchor(object(cap.value().get("cut")),(String)cap.value().get("catalog"),(String)cap.value().get("application"));
            require(future.pending() && future.parent.equals(parent),"included retention future parent");
            require(future.record("accept.gsr").digest().equals(basis.value().get("accepted")),"included retention future original tail");
            for(var peer:future.peers)state.plan().possible(peer.identity());
        }
        return new Frozen(raw.promise,raw.state,state,futureBytes,future);
    }
    static Optional<String> futureReference(byte[] wrapper){return Optional.ofNullable(decode(wrapper).future);}
    /** Until selected installation owns these proofs, even a legacy local owner
     * must not accept a new decision that would omit a remote obligation. */
    static void requireSelectable(MembershipSelection.Source source) {
        for(String key:source.capsule.packet.objectNames()) {
            int size=source.capsule.packet.objectSize(key);if(size<4 || size>MAXIMUM)continue;
            byte[] bytes=source.capsule.packet.objectBytes(key);if(ByteBuffer.wrap(bytes).getInt()!=MAGIC)continue;
            Raw raw;try{raw=decode(bytes);}catch(IllegalArgumentException invalid){continue;}
            if(Objects.equals(raw.promise.value().get("basisId"),source.basis.value().get("basisId")))
                require(raw.future==null,"selected future retention propagation required");
        }
    }
    private MembershipPeerRetentionSource() {}
}
