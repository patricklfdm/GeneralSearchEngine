package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Short real backup/TCP history in the explicit segmented layout; no full joining claim. */
class V53SegmentedNativeSeedTest {
    @TempDir Path temp;
    @Test void nonemptyNativeBarrierRecordsSegmentedWireAndClosesOriginalOwners()throws Exception {
        String[] keys={"v53.transport.connections","v53.resource.transitions","v53.resource.owner.close"};
        var before=new HashMap<String,String>();for(String key:keys){before.put(key,System.getProperty(key));System.setProperty(key,"true");}
        try {
            var seed=new V53NativeSeedTest();seed.temp=temp;var request=seed.request(5,true);
            var original=V53ReplayFilesTest.files(request.sourcePath().orElseThrow());
            var helper=new V53NativeDispatchTest();helper.temp=temp;var driver=new V53RoundDriverTest();driver.temp=temp;
            var n=helper.new Network(request,driver.controlBounds(),V53NativeDispatchTest.BUDGET,f->{},true,false,V53WireArchive.Layout.SEGMENTED_BACKUP);
            n.observeRequests=true;
            try(n;var round=driver.driver(n,MembershipRoundDriver.Events.NONE)) {
                assertInstanceOf(V53SegmentedEvidence.class,n.wire);assertInstanceOf(V53EvidenceSpool.class,n.events);
                assertEquals("PUBLISH_ACK",round.start().kind());assertEquals(MembershipRoundDriver.State.READY,round.state());
                for(int voter:n.voters) {
                    var floor=n.owners.get(voter).floorCopyCurrent();
                    assertEquals(V53NativeSeedTest.SEQUENCE,floor.capsule.context.catalog.get("applicationSequence"));
                    assertArrayEquals(n.f.original.seed.application(),floor.fileBytes(floor.capsule.terminal().application()+".image"));
                }
            }
            assertEquals(original,V53ReplayFilesTest.files(request.sourcePath().orElseThrow()));
            for(var resources:n.resources)assertEquals(0,resources.usage().leases());
            assertTrue(Files.isRegularFile(n.f.raw.resolve(V53WireArchive.DIRECTORY).resolve("index.json")));
            assertFalse(Files.exists(n.f.raw.resolve("wire.json")));
            Files.write(n.f.raw.resolve("segmented-seed-result.json"),canonical(Map.of("status","PASS","source","VERIFIED_DURABLE_BACKUP",
                "size",5,"applicationSequence",V53NativeSeedTest.SEQUENCE,"fullJoiningQualified",false,"phase3Complete",false),4096));
            System.out.println("v53SegmentedNativeSeed="+n.f.raw.toAbsolutePath());
        }finally{for(String key:keys){String value=before.get(key);if(value==null)System.clearProperty(key);else System.setProperty(key,value);}}
    }
    @Test void segmentedLayoutCannotBeSelectedForAnEmptySource()throws Exception {
        var seed=new V53NativeSeedTest();seed.temp=temp;var request=seed.request(5,false);
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        assertThrows(AssertionError.class,()->helper.new Network(request,ReplicationBounds.defaults(),V53NativeDispatchTest.BUDGET,
            f->{throw new AssertionError("preparation reached");},true,false,V53WireArchive.Layout.SEGMENTED_BACKUP));
        V53BootstrapSeedTest.absent(request);
    }
}
