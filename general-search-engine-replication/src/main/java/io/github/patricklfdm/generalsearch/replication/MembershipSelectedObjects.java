package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Reachable immutable objects of an already authenticated prefix. This is a
 * new selected-generation materialization, never permission to edit an original
 * source, current generation, pending context or governing floor in place. */
final class MembershipSelectedObjects {
    static SortedMap<String,byte[]> prefix(MembershipCapsule original) {
        var packet=original.packet;var cap=packet.capsule().value();var keep=new TreeMap<String,byte[]>();
        add(packet,keep,original.context.recordRootDigest());add(packet,keep,(String)cap.get("initial"));add(packet,keep,(String)cap.get("catalog"));
        for(Object raw:list(cap.get("items"))) {
            var item=object(raw);add(packet,keep,(String)item.get("statement"));
            for(Object acknowledgement:list(item.get("endorsements")))add(packet,keep,(String)acknowledgement);
            if(item.get("kind").equals("MEMBERSHIP")) {
                add(packet,keep,(String)item.get("descriptor"));String hash=(String)item.get("certificate");add(packet,keep,hash);
                var certificate=decode(keep.get(hash),"records","CERTIFICATE");
                var proof=new TreeMap<>(certificate.value());proof.remove("proofs");
                add(packet,keep,MembershipFormat.hash(encode("records","PROOF",proof)));
                var accept=new TreeMap<>(proof);accept.remove("accepts");add(packet,keep,MembershipFormat.hash(encode("records","ACCEPT",accept)));
                String entry=(String)certificate.value().get("entry");add(packet,keep,entry);
                add(packet,keep,(String)decode(keep.get(entry),"records","ENTRY").value().get("payload"));
            }
        }
        return keep;
    }
    private static void add(MembershipSourcePacket packet,Map<String,byte[]> objects,String key) {
        require(key!=null && packet.objectNames().contains(key),"selected reachable original object missing");
        byte[] value=packet.objectBytes(key);require(hash(value).equals(key),"selected reachable original object changed");objects.put(key,value);
    }
    private MembershipSelectedObjects() {}
}
