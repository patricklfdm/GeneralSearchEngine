package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Pure admission for the next capture while an original pending context is pinned.
 * Adds the exact original inventory, never earlier backing packets recursively. No force,
 * grant, ownership observation, source retirement or permission to replace a pending vote. */
final class MembershipPendingTransfer {
    static final class Capture {
        private final MembershipCapsule capsule;
        private final Map<String,byte[]> images;
        private Capture(MembershipCapsule capsule,Map<String,byte[]> images) {
            this.capsule=capsule;this.images=copy(images);
        }
        MembershipCapsule capsule(){return capsule;}
        Map<String,byte[]> images(){return copy(images);}
    }
    private static Map<String,byte[]> copy(Map<String,byte[]> images) {
        var result=new TreeMap<String,byte[]>();images.forEach((h,b)->result.put(h,b.clone()));
        return Collections.unmodifiableMap(result);
    }
    private static void add(Map<String,byte[]> target,String digest,byte[] bytes) {
        require(hash(bytes).equals(digest),"pending transfer object hash");
        byte[] old=target.putIfAbsent(digest,bytes);
        require(old==null || Arrays.equals(old,bytes),"pending transfer conflicting original bytes");
    }

    static Capture capture(MembershipPendingContext.Reconstructed original,MembershipCapsule current,
            Map<String,byte[]> currentImages,MembershipCurrentGeneration.Verifier verifier) {
        Objects.requireNonNull(original);Objects.requireNonNull(current);Objects.requireNonNull(verifier);
        require(current.context.root.equals(original.capsule().context.root)
                && current.terminal().equals(original.capsule().terminal()),"pending transfer changed root/parent");
        current.packet.verifyImages(currentImages);
        var images=copyMutable(currentImages);var files=original.originalFiles();
        for(String digest:original.capsule().packet.images().keySet())
            add(images,digest,files.get(digest+".image"));
        // Admission precedes construction of the contiguous packet and any caller I/O.
        require(images.size()<=7,"pending transfer image capacity");
        var lengths=new TreeMap<String,Long>();images.forEach((h,b)->lengths.put(h,(long)b.length));
        var objects=new TreeMap<String,byte[]>();
        for(String digest:current.packet.objectNames())add(objects,digest,current.packet.objectBytes(digest));
        for(String digest:original.capsule().packet.objectNames())add(objects,digest,original.capsule().packet.objectBytes(digest));
        var vote=original.vote();add(objects,vote.entry().digest(),vote.entry().bytes());
        add(objects,vote.accept().digest(),vote.accept().bytes());add(objects,hash(vote.payload()),vote.payload());
        if(vote.proof()!=null)add(objects,vote.proof().digest(),vote.proof().bytes());
        if(vote.certificate()!=null)add(objects,vote.certificate().digest(),vote.certificate().bytes());
        var value=new TreeMap<>(current.packet.capsule().value());
        value.put("inventory",hash(MembershipSourcePacket.index(objects,lengths)));
        var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(decode(encode("records","CAPSULE",value),
                "records","CAPSULE"),objects,lengths));
        var root=decode(current.packet.objectBytes(current.context.recordRootDigest()),"records","ROOT");
        var capsule=Objects.requireNonNull(verifier.verify(root,packet,copy(images)),"pending transfer verifier returned null");
        require(Arrays.equals(packet.bytes(),capsule.packet.bytes()) && capsule.terminal().equals(current.terminal()),
                "pending transfer verifier substituted capture");
        require(Arrays.equals(original.capsule().packet.bytes(),MembershipSourcePacket.reconstruct(
                original.capsule().packet.envelope(),packet).bytes()),"pending transfer changed original packet");
        return new Capture(capsule,images);
    }
    private static Map<String,byte[]> copyMutable(Map<String,byte[]> input) {
        return new TreeMap<>(copy(input));
    }
    private MembershipPendingTransfer() {}
}
