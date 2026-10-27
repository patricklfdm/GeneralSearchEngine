package io.github.patricklfdm.generalsearch.replication;

import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Conditional format histories exercise the complete typed reachability graph.
 * Native originals and process recovery are separately required. */
class V53SelectedObjectsTest {
    @Test void everyPrefixPreservesAllSevenTransitionProofsWithoutAccumulatedOpaqueObjects() {
        for(Object[] profile:new Object[][]{{3,"ADD"},{4,"ADD"},{4,"REMOVE"},{5,"REMOVE"},
                {3,"REPLACE"},{4,"REPLACE"},{5,"REPLACE"}})for(int cut=0;cut<=9;cut++) {
            var fixture=new V53CapsuleFixture((int)profile[0],(String)profile[1],cut);
            var mandatory=new TreeSet<>(fixture.objects.keySet());
            // The complete pre-compaction history has old catalogs, ordinary
            // entries and earlier per-vote records absent from the live prefix.
            fixture.source.inventory.forEach(fixture.objects::putIfAbsent);
            byte[] opaque=("old election object "+cut).getBytes(StandardCharsets.UTF_8);
            fixture.objects.put(hash(opaque),opaque);
            var original=fixture.verify();byte[] unchanged=original.packet.bytes();
            var retained=MembershipSelectedObjects.prefix(original);
            assertEquals(mandatory,retained.keySet(),profile[1]+" cut "+cut);
            for(String key:mandatory)assertArrayEquals(original.packet.objectBytes(key),retained.get(key));
            var cap=new TreeMap<>(original.packet.capsule().value());
            cap.put("inventory",hash(MembershipSourcePacket.index(retained,original.packet.images())));
            var packet=MembershipSourcePacket.decode(MembershipSourcePacket.encode(
                    decode(encode("records","CAPSULE",cap),"records","CAPSULE"),retained,original.packet.images()));
            var rebuilt=original.materialization(packet,fixture.source.images,List.of());
            assertEquals(original.terminal(),rebuilt.terminal());
            assertEquals(original.anchors(),rebuilt.anchors());
            assertEquals(original.membershipCertificateFence().map(Decoded::digest),rebuilt.membershipCertificateFence().map(Decoded::digest));
            assertArrayEquals(unchanged,original.packet.bytes(),"selection must not rewrite an immutable source");
            assertEquals(retained.keySet(),MembershipSelectedObjects.prefix(rebuilt).keySet());
        }
    }
    @Test void rootIdentityIsNotTheFullOriginalRecordDigestAndReturnedBytesAreIndependent() {
        var fixture=new V53CapsuleFixture(3,"ADD",0);var original=fixture.verify();
        assertNotEquals(original.context.root,fixture.source.root.digest());
        var retained=MembershipSelectedObjects.prefix(original);
        assertTrue(retained.containsKey(fixture.source.root.digest()));
        byte[] before=original.packet.bytes();retained.get(fixture.source.root.digest())[0]^=1;retained.clear();
        assertArrayEquals(before,original.packet.bytes());
        assertArrayEquals(fixture.source.root.bytes(),MembershipSelectedObjects.prefix(original).get(fixture.source.root.digest()));
    }
}
