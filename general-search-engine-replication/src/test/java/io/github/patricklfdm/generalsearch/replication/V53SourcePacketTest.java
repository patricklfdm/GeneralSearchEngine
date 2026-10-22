package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53ContextFixture.*;
import java.nio.ByteBuffer;
import java.util.*;
import org.junit.jupiter.api.Test;

class V53SourcePacketTest {
    static final class Fixture {
        final V53ContextFixture f=new V53ContextFixture(3,"ADD");
        final Map<String,byte[]> objects=new TreeMap<>();final Map<String,Long> images=new TreeMap<>();
        final Decoded capsule;final String accepted;
        Fixture() {this(false);}
        Fixture(boolean tail) {
            var catalog=f.catalog();objects.putAll(f.inventory);f.images.forEach((h,b)->images.put(h,(long)b.length));
            if(tail) {
                byte[] payload=command("BARRIER",(Object)null);objects.put(hash(payload),payload);
                byte[] entry=encode("records","ENTRY",map("authority",f.context().authority(),"index",1L,"kind","BARRIER","origin",f.ballot(1),
                        "payload",hash(payload),"previous",object(f.state.get("cut")).get("entry"),"root",f.rootHash));objects.put(hash(entry),entry);
                byte[] accept=encode("records","ACCEPT",map("authority",f.context().authority(),"ballot",f.ballot(1),"entry",hash(entry),"index",1L,"root",f.rootHash));
                accepted=hash(accept);objects.put(accepted,accept);
            } else accepted=null;
            var body=map("application",f.state.get("application"),"catalog",catalog.digest(),"cut",f.state.get("cut"),
                    "initial",f.root.value().get("genesis"),"inventory",hash(MembershipSourcePacket.index(objects,images)),"items",List.of(),"root",f.rootHash);
            capsule=decode(encode("records","CAPSULE",body),"records","CAPSULE");
        }
        byte[] bytes() {return MembershipSourcePacket.encode(capsule,objects,images);}
        Decoded basis() {
            return f.record("BASIS",map("accepted",accepted,"ballot",f.ballot(1),"basisId",new UUID(7,8).toString(),"capsule",capsule.digest(),
                    "cut",f.state.get("cut"),"inventory",capsule.value().get("inventory"),"root",f.rootHash,"view",f.context().authority(),"voter","node-1"));
        }
    }
    static byte[] checksum(byte[] bytes) {
        System.arraycopy(sha(Arrays.copyOf(bytes,16),Arrays.copyOfRange(bytes,48,bytes.length)),0,bytes,16,32);return bytes;
    }
    @Test void deterministicPacketBindsSeparateImagesAndExactOriginalBasis() {
        var f=new Fixture();byte[] bytes=f.bytes();assertArrayEquals(bytes,f.bytes());
        var packet=MembershipSourcePacket.decode(bytes);packet.bind(f.basis());packet.verifyImages(f.f.images);
        assertEquals(f.objects.keySet(),packet.objectNames());assertEquals(f.images,packet.images());
        assertArrayEquals(f.capsule.bytes(),packet.capsule().bytes());
        var hash=f.objects.keySet().iterator().next();byte[] copy=packet.objectBytes(hash);copy[0]^=1;
        assertArrayEquals(f.objects.get(hash),packet.objectBytes(hash));
        assertThrows(UnsupportedOperationException.class,()->packet.objectNames().clear());
        assertThrows(UnsupportedOperationException.class,()->packet.images().clear());
        for(String field:List.of("root","capsule","inventory","cut","accepted")) {
            var basis=object(mutable(f.basis().value()));
            if(field.equals("cut"))object(basis.get("cut")).put("index",1L);else basis.put(field,H);
            var altered=f.f.record("BASIS",basis);assertThrows(IllegalArgumentException.class,()->packet.bind(altered),field);
        }
        assertThrows(IllegalArgumentException.class,()->packet.verifyImages(Map.of()));
        var bad=new HashMap<>(f.f.images);String image=bad.keySet().iterator().next();byte[] changed=bad.get(image).clone();changed[0]^=1;bad.put(image,changed);
        assertThrows(IllegalArgumentException.class,()->packet.verifyImages(bad));
    }
    @Test void sizeAndLengthTamperingRejectsBeforeAnyMemberAllocation() {
        var f=new Fixture();byte[] original=f.bytes();
        for(int offset:new int[]{0,4,6,8,10,12,48}) {
            byte[] bad=original.clone();bad[offset]^=(byte)128;checksum(bad);
            assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.decode(bad),"header offset "+offset);
        }
        int indexLengthOffset=52+ByteBuffer.wrap(original).getInt(48);
        byte[] oversized=original.clone();ByteBuffer.wrap(oversized).putInt(indexLengthOffset,Integer.MAX_VALUE);checksum(oversized);
        assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.decode(oversized));
        byte[] truncated=Arrays.copyOf(original,original.length-1);ByteBuffer.wrap(truncated).putInt(12,truncated.length-48);checksum(truncated);
        assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.decode(truncated));
        byte[] extra=Arrays.copyOf(original,original.length+1);ByteBuffer.wrap(extra).putInt(12,extra.length-48);checksum(extra);
        assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.decode(extra));
        byte[] corrupt=original.clone();corrupt[corrupt.length-1]^=1;checksum(corrupt);
        assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.decode(corrupt));
    }
    @Test void ownedTailNeedsOriginalEntryPayloadParentAndOrderedBallots() {
        var f=new Fixture(true);MembershipSourcePacket.decode(f.bytes()).bind(f.basis());
        for(String change:List.of("parent","accept-ballot","entry-origin","missing-payload","barrier-payload")) {
            var objects=new TreeMap<>(f.objects);var accept=object(mutable(decode(objects.get(f.accepted),"records","ACCEPT").value()));
            var entry=object(mutable(decode(objects.get((String)accept.get("entry")),"records","ENTRY").value()));
            switch(change) {
                case "parent" -> entry.put("previous",H);
                case "accept-ballot" -> accept.put("ballot",f.f.ballot(2));
                case "entry-origin" -> entry.put("origin",f.f.ballot(2));
                case "missing-payload" -> objects.remove(entry.get("payload"));
                case "barrier-payload" -> {byte[] bytes={1};objects.put(hash(bytes),bytes);entry.put("payload",hash(bytes));}
            }
            byte[] entryBytes=encode("records","ENTRY",entry);objects.put(hash(entryBytes),entryBytes);accept.put("entry",hash(entryBytes));
            byte[] acceptBytes=encode("records","ACCEPT",accept);objects.put(hash(acceptBytes),acceptBytes);
            var cap=object(mutable(f.capsule.value()));cap.put("inventory",hash(MembershipSourcePacket.index(objects,f.images)));
            var capsule=decode(encode("records","CAPSULE",cap),"records","CAPSULE");
            var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(capsule,objects,f.images));
            var basis=object(mutable(f.basis().value()));basis.put("accepted",hash(acceptBytes));basis.put("capsule",capsule.digest());basis.put("inventory",cap.get("inventory"));
            var changed=f.f.record("BASIS",basis);assertThrows(IllegalArgumentException.class,()->packet.bind(changed),change);
        }
    }
    @Test void inventoryDoesNotInlineApplicationBytesOrAcceptUnknownAndDuplicateMembers() {
        var f=new Fixture();String image=f.images.keySet().iterator().next();f.images.put(image,64*1024*1024L);
        byte[] index=MembershipSourcePacket.index(f.objects,f.images);assertTrue(index.length<1024);
        f.images.put(image,64*1024*1024L+1);assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.index(f.objects,f.images));
        var packet=new Fixture();byte[] bytes=packet.bytes();int start=56+ByteBuffer.wrap(bytes).getInt(48),length=ByteBuffer.wrap(bytes).getInt(start-4);
        var original=object(mutable(parse(Arrays.copyOfRange(bytes,start,start+length),1024*1024)));
        for(String change:List.of("duplicate","order","negative","overflow","unknown","kind")) {
            var value=object(mutable(original));var rows=new ArrayList<Object>(list(value.get("objects")));
            switch(change) {
                case "duplicate" -> rows.add(rows.getFirst());
                case "order" -> Collections.reverse(rows);
                case "negative" -> object(rows.getFirst()).put("bytes",-1L);
                case "overflow" -> object(rows.getFirst()).put("bytes",Long.MAX_VALUE);
                case "unknown" -> value.put("paths",List.of("../outside"));
                case "kind" -> object(rows.getFirst()).put("sha256",1L);
            }
            value.put("objects",rows);byte[] replacement=canonical(value,1024*1024);byte[] bad=new byte[bytes.length-length+replacement.length];
            System.arraycopy(bytes,0,bad,0,start);System.arraycopy(replacement,0,bad,start,replacement.length);
            System.arraycopy(bytes,start+length,bad,start+replacement.length,bytes.length-start-length);
            ByteBuffer.wrap(bad).putInt(start-4,replacement.length).putInt(12,bad.length-48);checksum(bad);
            assertThrows(IllegalArgumentException.class,()->MembershipSourcePacket.decode(bad),change);
        }
    }
}
