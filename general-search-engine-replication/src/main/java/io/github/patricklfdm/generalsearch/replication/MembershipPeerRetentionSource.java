package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import java.util.function.Function;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Exact pre-PROMISE local retention snapshot inside the immutable source index.
 * This authenticates which local bytes were frozen, not a quorum intent, a peer
 * progress observation, or permission to discard any other selected obligation. */
final class MembershipPeerRetentionSource {
    static final int MAGIC=0x47535250,MAXIMUM=HEADER+8+8192+MembershipPeerRetentionFiles.MAXIMUM;
    record Frozen(Decoded promise,byte[] localBytes,MembershipPeerRetentionFiles.State state,byte[] futureBytes,
            MembershipFutureRetentionFiles.State future,List<MembershipFutureRetentionSet.Proof> inherited,byte[] projection) {
        Frozen {localBytes=localBytes.clone();futureBytes=futureBytes==null?null:futureBytes.clone();inherited=List.copyOf(inherited);projection=projection==null?null:projection.clone();}
        @Override public byte[] localBytes(){return localBytes.clone();}
        @Override public byte[] futureBytes(){return futureBytes==null?null:futureBytes.clone();}
        @Override public byte[] projection(){return projection==null?null:projection.clone();}
        List<MembershipFutureRetentionSet.Proof> proofs(){return future==null?inherited:List.of(new MembershipFutureRetentionSet.Proof(futureBytes,future));}
        Map<String,byte[]> objects(){var result=new TreeMap<String,byte[]>();proofs().forEach(p->result.put(hash(p.bytes()),p.bytes()));if(projection!=null)result.put(hash(projection),projection.clone());return result;}
    }
    private record Raw(Decoded promise,byte[] state,String future,int flags) {}
    static byte[] wrapper(Frozen value){return encode(value.promise,value.localBytes,
            value.projection!=null?hash(value.projection):value.futureBytes==null?null:hash(value.futureBytes),value.projection!=null?2:value.futureBytes==null?0:1);}
    private static byte[] encode(Decoded promise,byte[] localBytes,String future) {return encode(promise,localBytes,future,future==null?0:1);}
    private static byte[] encode(Decoded promise,byte[] localBytes,String future,int flags) {
        require(promise.family().equals("records") && promise.kind().equals("PROMISE")
                && promise.value().get("basisId")!=null,"retention source requires capture promise");
        byte[] p=promise.bytes();require(p.length<=8192 && localBytes.length<=MembershipPeerRetentionFiles.MAXIMUM,"retention source bounds");
        var buffer=ByteBuffer.allocate(8+p.length+localBytes.length+(future==null?0:32)).putInt(p.length).put(p).putInt(localBytes.length).put(localBytes);
        if(future!=null){MembershipValidation.digest(future);buffer.put(HexFormat.of().parseHex(future));}
        byte[] body=buffer.array();require(HEADER+body.length<=MAXIMUM,"retention source total capacity");
        byte[] prefix=ByteBuffer.allocate(16).putInt(MAGIC).putShort((short)1).putShort((short)3).putInt(flags).putInt(body.length).array();
        return ByteBuffer.allocate(HEADER+body.length).put(prefix).put(sha(prefix,body)).put(body).array();
    }
    private static Raw decode(byte[] bytes) {
        require(bytes.length>HEADER+8 && bytes.length<=MAXIMUM,"retention source extent");var b=ByteBuffer.wrap(bytes);
        require(b.getInt()==MAGIC && b.getShort()==1 && b.getShort()==3,"retention source framing");
        int flags=b.getInt();require((flags>=0 && flags<=2) && b.getInt()==bytes.length-HEADER,"retention source framing");
        byte[] body=Arrays.copyOfRange(bytes,HEADER,bytes.length);
        require(Arrays.equals(Arrays.copyOfRange(bytes,16,HEADER),sha(Arrays.copyOf(bytes,16),body)),"retention source checksum");
        b.position(HEADER);int n=b.getInt();require(n>=HEADER && n<=8192 && n<=b.remaining()-4,"retention source promise extent");
        byte[] p=new byte[n];b.get(p);var promise=MembershipFormat.decode(p,"records","PROMISE");
        n=b.getInt();require(n>MembershipPeerRetentionFiles.HEADER && n<=MembershipPeerRetentionFiles.MAXIMUM && n==b.remaining()-(flags!=0?32:0),"retention source state extent");
        byte[] state=new byte[n];b.get(state);String future=null;
        if(flags!=0){byte[] digest=new byte[32];b.get(digest);future=HexFormat.of().formatHex(digest);}
        require(Arrays.equals(bytes,encode(promise,state,future,flags)),"retention source noncanonical bytes");return new Raw(promise,state,future,flags);
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
        return read(source.capsule.packet,source.basis,source.owner);
    }
    /** Reads a locally retained original, including its exact BASIS envelope. */
    static Frozen read(MembershipSourcePacket packet,Decoded basis,MembershipIdentity owner) {
        packet.bind(basis);var expected=basis.value();Raw found=null;
        // The complete packet is already bounded. No optional hint or live mutable
        // state can substitute for the exact object committed by this BASIS index.
        for(String key:packet.objectNames()) {
            int n=packet.objectSize(key);if(n<4 || n>MAXIMUM)continue;
            byte[] bytes=packet.objectBytes(key);if(ByteBuffer.wrap(bytes).getInt()!=MAGIC)continue;
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
        return includedObjects(packet.envelope(),basis,owner,
                encode(found.promise,found.state,found.future,found.flags),h->{
                    require(packet.objectNames().contains(h),"retention source future proof missing");
                    require(packet.objectSize(h)<=MembershipFutureRetentionFiles.MAXIMUM,"retention source future proof extent");
                    return packet.objectBytes(h);
                });
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
        require(raw.flags<=1,"inherited future needs complete original objects");
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
        return new Frozen(raw.promise,raw.state,state,futureBytes,future,List.of(),null);
    }
    static Frozen includedObjects(byte[] envelope,Decoded basis,MembershipIdentity owner,byte[] wrapper,Function<String,byte[]> reader) {
        var raw=decode(wrapper);
        if(raw.flags!=2)return included(envelope,basis,owner,wrapper,raw.future==null?null:reader.apply(raw.future));
        var cap=MembershipSourcePacket.included(envelope,basis,wrapper);
        for(String field:List.of("root","view","ballot","basisId"))
            require(raw.promise.value().get(field).equals(basis.value().get(field)),"included retention original promise binding");
        require(basis.value().get("voter").equals(owner.nodeId().value()),"included retention source owner");
        String root=(String)cap.value().get("root");var state=MembershipPeerRetentionFiles.decodeOwned(raw.state,root,owner);
        byte[] projection=reader.apply(raw.future);require(projection!=null && hash(projection).equals(raw.future),"inherited future descriptor missing/digest");
        MembershipSourcePacket.included(envelope,basis,projection);
        var proofs=MembershipFutureRetentionSet.decode(projection,root,owner,h->{byte[] original=reader.apply(h);MembershipSourcePacket.included(envelope,basis,original);return original;});
        var parent=new MembershipCapsule.Anchor(object(cap.value().get("cut")),(String)cap.value().get("catalog"),(String)cap.value().get("application"));
        String accepted=(String)basis.value().get("accepted");require(accepted!=null,"inherited future carried acceptance missing");
        byte[] acceptedBytes=reader.apply(accepted);MembershipSourcePacket.included(envelope,basis,acceptedBytes);
        var accept=MembershipFormat.decode(acceptedBytes,"records","ACCEPT");require(accept.digest().equals(accepted),"inherited future carried acceptance digest");
        MembershipCapsule.Anchor target=null;
        for(var proof:proofs) {
            var future=proof.state();state.plan().possible(future.owner);
            require(future.parent.equals(parent) && future.record("entry.gsr").digest().equals(accept.value().get("entry")),"inherited future carried parent/entry");
            require(target==null || target.equals(future.target()),"inherited future conflicting target");target=future.target();
            future.peers.forEach(peer->state.plan().possible(peer.identity()));
        }
        return new Frozen(raw.promise,raw.state,state,null,null,proofs,projection);
    }
    static MembershipSourcePacket freezeInherited(MembershipSourcePacket original,Decoded promise,MembershipIdentity owner,byte[] localBytes,
            Collection<MembershipFutureRetentionSet.Proof> proofs) {
        if(proofs.isEmpty())return freeze(original,promise,owner,localBytes);
        MembershipPeerRetentionFiles.decodeOwned(localBytes,(String)original.capsule().value().get("root"),owner);
        require(promise.value().get("root").equals(original.capsule().value().get("root")),"inherited future foreign promise");
        byte[] descriptor=MembershipFutureRetentionSet.encode((String)promise.value().get("root"),owner,proofs);
        var objects=new TreeMap<String,byte[]>();for(String h:original.objectNames())objects.put(h,original.objectBytes(h));
        proofs.forEach(proof->objects.put(hash(proof.bytes()),proof.bytes()));objects.put(hash(descriptor),descriptor);
        byte[] captured=encode(promise,localBytes,hash(descriptor),2);objects.put(hash(captured),captured);
        var cap=new TreeMap<>(original.capsule().value());cap.put("inventory",hash(MembershipSourcePacket.index(objects,original.images())));
        return MembershipSourcePacket.decode(MembershipSourcePacket.encode(MembershipFormat.decode(MembershipFormat.encode("records","CAPSULE",cap),"records","CAPSULE"),objects,original.images()));
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
