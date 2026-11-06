package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** Conditional collector guards only; the separate native test supplies actual lifetimes. */
class V53NativeResourceRefusalCaptureTest {
    @TempDir Path temp;
    @Test void physicalPathsAreValuesRatherThanRestrictedJsonObjectKeys() {
        String path="sources/11111111-2222-3333-4444-555555555555/"+"a".repeat(64)+".image";
        var rows=V53NativeResourceRefusalCapture.fileIdentities(Map.of(path,"b".repeat(64)));
        byte[] bytes=MembershipFormat.canonical(Map.of("authorityFiles",rows),65536);
        assertTrue(new String(bytes,java.nio.charset.StandardCharsets.UTF_8).contains(path));
        assertEquals(List.of(Map.of("path",path,"sha256","b".repeat(64))),rows);
    }
    @Test void realReceiverRefusesFullSourcePoolAndReturnsItsTemporaryControl()throws Exception {
        var f=new V53SourcePacketTest.Fixture();var packet=MembershipSourcePacket.decode(f.bytes());
        var resources=new MembershipResources(512*MembershipResources.MIB);var held=new ArrayList<MembershipResources.Lease>();
        try {
            for(int n=0;n<6;n++)held.add(resources.reserve(MembershipResources.Unit.SOURCE,"held-"+n,1));
            var before=resources.usage();
            V53NativeResourceRefusalCapture.refuse(temp.resolve("receiver"),f.f.rootHash,V53DeclarationsTest.node(1),packet,resources);
            assertEquals(before,resources.usage());assertFalse(Files.exists(temp.resolve("receiver")));
        }finally{held.forEach(MembershipResources.Lease::close);}
        assertEquals(0,resources.usage().leases());
    }
    @Test void availableCapacityCannotBeMisreportedAsRejection()throws Exception {
        var f=new V53SourcePacketTest.Fixture();var resources=new MembershipResources(512*MembershipResources.MIB);
        assertThrows(AssertionError.class,()->V53NativeResourceRefusalCapture.refuse(temp.resolve("receiver"),f.f.rootHash,
                V53DeclarationsTest.node(1),MembershipSourcePacket.decode(f.bytes()),resources));
        assertEquals(0,resources.usage().leases());assertFalse(Files.exists(temp.resolve("receiver")));
    }
    @Test void otherCapacityFailureCannotReceiveCountRefusalCredit()throws Exception {
        var f=new V53SourcePacketTest.Fixture();var resources=new MembershipResources(1);
        var error=assertThrows(IllegalArgumentException.class,()->V53NativeResourceRefusalCapture.refuse(temp.resolve("receiver"),f.f.rootHash,
                V53DeclarationsTest.node(1),MembershipSourcePacket.decode(f.bytes()),resources));
        assertEquals("native refusal exact count rejection: shared staging capacity",error.getMessage());
        assertEquals(0,resources.usage().leases());assertFalse(Files.exists(temp.resolve("receiver")));
    }
}
