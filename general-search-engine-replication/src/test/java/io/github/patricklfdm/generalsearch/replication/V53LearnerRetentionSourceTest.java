package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

class V53LearnerRetentionSourceTest {
    @TempDir Path temp;
    V53BootstrapPublicationTest.Fixture fixture(String name)throws Exception {
        var raw=Files.createDirectories(Path.of("target/v53-learner-selection/run-"+UUID.randomUUID()).resolve(name));
        System.out.println("v53LearnerSelectionEvidence="+raw.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(Files.createDirectory(temp.resolve(name)),raw,3,false);f.ownedHistory=true;
        return f;
    }
    static Map<String,Object> ballot(V53BootstrapPublicationTest.Fixture f)throws Exception {
        var first=f.request.targets().getFirst();try(var owner=f.open(first,"allocate")) {
            return Map.of("counter",owner.reserveCounter(),"proposer",first.identity().nodeId().value(),"incarnation",first.identity().storageId().toString());
        }
    }
    @Test void exactFrozenBytesBindOriginalOwnerPromiseAndInventory()throws Exception {
        var f=fixture("binding");var first=f.request.targets().getFirst();
        try(var owner=f.open(first,"init")){owner.initializeLearnerRetention();}
        var ballot=ballot(f);
        try(var owner=f.open(first,"capture")) {
            byte[] local=Files.readAllBytes(first.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE));
            owner.prepareCurrent(ballot);var source=owner.originalSource();var frozen=MembershipLearnerRetentionSource.read(source);
            assertArrayEquals(local,frozen.localBytes());assertEquals(0,frozen.state().revision());
            var wrapper=MembershipLearnerRetentionSource.wrapper(frozen);
            assertArrayEquals(local,MembershipLearnerRetentionSource.included(source.capsule.packet.envelope(),source.basis,first.identity(),wrapper).localBytes());
            byte[] changed=frozen.localBytes();changed[0]^=1;assertArrayEquals(local,frozen.localBytes());
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionSource.included(source.capsule.packet.envelope(),source.basis,f.request.targets().get(1).identity(),wrapper));
            wrapper[wrapper.length-1]^=1;
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionSource.included(source.capsule.packet.envelope(),source.basis,first.identity(),wrapper));
            assertThrows(IllegalArgumentException.class,()->MembershipLearnerRetentionSource.requireLegacyCompatible(source));
            assertArrayEquals(local,Files.readAllBytes(first.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE)));
        }
        assertEquals(0,f.resources.usage().leases());
    }
    @Test void interruptedSourceCaptureRecoversTheSameBoundedLedgerSnapshot()throws Exception {
        for(String cut:List.of("CAPTURE_INTENT_PREFIX_WRITTEN","SOURCE_PACKET_FORCED","BASIS_FORCED")) {
            var f=fixture(cut);var first=f.request.targets().getFirst();byte[] local;
            try(var owner=f.open(first,"init")){owner.initializeLearnerRetention();local=Files.readAllBytes(first.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE));}
            var ballot=ballot(f);f.observer=(target,operation,event)->{if(event.equals(cut))throw new IOException("capture cut");};
            try(var owner=f.open(first,"capture")){assertThrows(IOException.class,()->owner.prepareCurrent(ballot));}
            f.observer=(target,operation,event)->{};f.snapshot("interrupted");
            try(var owner=f.open(first,"recovered")) {
                var source=owner.originalSource();var frozen=MembershipLearnerRetentionSource.read(source);
                assertArrayEquals(local,frozen.localBytes());assertEquals(ballot,frozen.promise().value().get("ballot"));
                var original=source.basis.bytes();assertArrayEquals(original,owner.prepareCurrent(ballot).bytes());
                assertArrayEquals(local,Files.readAllBytes(first.replicaDirectory().resolve(MembershipLearnerRetentionFiles.FILE)));
            }
            f.snapshot("recovered");assertEquals(0,f.resources.usage().leases());
        }
    }
    @Test void missingSnapshotsAndLegacyOwnersCannotSilentlyDiscardObligations()throws Exception {
        var f=fixture("mixed");var first=f.request.targets().getFirst();
        try(var owner=f.open(first,"init")){owner.initializeLearnerRetention();}
        var ballot=ballot(f);var sources=new ArrayList<MembershipSelection.Source>();
        for(var target:f.request.targets())try(var owner=f.open(target,"capture")){owner.prepareCurrent(ballot);sources.add(owner.originalSource());}
        for(var target:f.request.targets())try(var owner=f.open(target,"refuse-mixed")) {
            var before=V53ReplayFilesTest.files(target.replicaDirectory());
            var error=assertThrows(IllegalArgumentException.class,()->owner.selectCurrent(sources,List.of()));
            assertTrue(error.getMessage().contains(target.equals(first)?"original snapshot missing":"propagation required"));
            assertEquals(before,V53ReplayFilesTest.files(target.replicaDirectory()));assertTrue(owner.originalSelection().isEmpty());
        }
        assertEquals(0,f.resources.usage().leases());
    }
}
