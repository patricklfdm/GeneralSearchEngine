package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfSystemProperty;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Explicit original-copy recovery before automatic campaigning. This is not
 * automatic discovery of missing partial-floor copies. */
@EnabledIfSystemProperty(named="v53.partial.floor.resume",matches="true")
class V53PartialFloorResumeTest {
    @TempDir Path temp;
    @Test void exactOriginalFloorResumesBeforeRequiredVoterContinues()throws Exception {
        var scenario=new V53CombinedResourceRecoveryTest();scenario.temp=temp;scenario.run(true);
    }
    static void resume(V53BootstrapPublicationTest.Fixture retained,Path raw)throws Exception {
        var f=new V53BootstrapPublicationTest.Fixture(raw,retained);f.snapshot("before");
        var copies=new ArrayList<MembershipFloor.Copy>();var originals=Files.createDirectory(raw.resolve("original-copies"));
        var usage=new ArrayList<Map<String,Object>>();
        f.observer=(target,operation,event)->{
            if(target.identity().nodeId().value().equals("node-2"))usage.add(Map.of("operation",operation,"event",event,
                "usage",V53CombinedReceiveResourcesTest.usage(f.resources)));
        };
        try {
            for(var target:f.request.targets())try(var owner=f.open(target,"original-copy")) {
                var copy=owner.floorCopyCurrent();copies.add(copy);
                Path path=Files.createDirectory(originals.resolve(target.identity().nodeId().value()));
                for(var file:copy.copyFiles().entrySet())Files.write(path.resolve(file.getKey()),file.getValue());
            }
            var target=f.request.targets().get(1);byte[] proposal=Files.readAllBytes(target.replicaDirectory().resolve("floor-copies/proposal.gsr"));
            Files.write(raw.resolve("original-proposal.gsr"),proposal);
            // This is another genuine same-cut governing quorum, but it is not
            // the one named by the already persisted proposal.
            try(var owner=f.open(target,"wrong-cohort")) {
                var error=assertThrows(IllegalArgumentException.class,()->owner.establishFloor(List.of(copies.get(0),copies.get(1),copies.get(3))));
                assertTrue(Set.of("floor requires exact original proposal","unrelated retained floor files").contains(error.getMessage()),error.toString());
                Files.write(raw.resolve("rejection.json"),canonical(Map.of("kind",error.getClass().getName(),"message",error.getMessage()),4096));
            }
            f.snapshot("after-rejection");
            for(var t:f.request.targets())assertEquals(V53CombinedResourceRecoveryTest.disk(raw.resolve("before/"+t.identity().nodeId().value())),
                V53CombinedResourceRecoveryTest.disk(t.replicaDirectory()),"refused proposal leaves all originals unchanged");
            try(var owner=f.open(target,"exact-resume")) {
                assertTrue(owner.governingFloor().isEmpty());
                var floor=owner.establishFloor(copies.subList(0,3));assertArrayEquals(proposal,floor.bytes());
                assertArrayEquals(proposal,owner.governingFloor().orElseThrow().bytes());
                assertEquals(7,f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }
            f.snapshot("resumed");
            assertEquals(0,f.resources.usage().leases());
            try(var owner=f.open(target,"cold-inspect")) {
                assertArrayEquals(proposal,owner.governingFloor().orElseThrow().bytes());
                assertEquals(7,f.resources.usage().counts().get(MembershipResources.Unit.APPLICATION));
            }
            f.snapshot("reopened");
            Files.write(raw.resolve("result.json"),canonical(Map.of("status","PASS","originalCopies",3,"applicationImages",7,
                "explicitOriginalCopyRecovery",true,"automaticRecovery",false,"pendingAcceptPreserved",true),4096));
        } finally {
            Files.write(raw.resolve("usage.json"),canonical(usage,1024*1024));V53NativeApplicationTest.save(f);
        }
    }
}
