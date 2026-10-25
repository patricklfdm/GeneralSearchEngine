package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Small-image regression for the same retained-source route as the maximal-image gate. */
class V53AdmittedCampaignAncestryTest {
    @TempDir Path temp;
    @Test void hiddenOriginalSourceIsBridgedIntoTheNextInstalledCampaign()throws Exception {
        Path out=Path.of("target/v53-admitted-campaign-ancestry/run-"+UUID.randomUUID());Files.createDirectories(out);
        System.out.println("v53AdmittedCampaignAncestryEvidence="+out.toAbsolutePath());
        var f=new V53BootstrapPublicationTest.Fixture(temp,out,5,false);
        try {
            var walk=new V53AdmittedCrossViewTest.Walk(f);
            walk.publish("BARRIER",null);walk.campaign();walk.publish("BARRIER",null);walk.campaign();
            for(var target:f.request.targets())try(var owner=f.open(target,"inspect-ancestry")) {
                var copy=owner.floorCopyCurrent();assertEquals(2L,copy.capsule.context.cut.get("index"));
                assertNull(copy.capsule.anchor(1));
                var anchors=copy.capsule.ancestryAnchors(copy.fileBytes("ancestry.gsr"));
                assertEquals(1,anchors.size());assertEquals(1L,anchors.values().iterator().next().cut().get("index"));
            }
            assertEquals(0,f.resources.usage().leases());
            Files.write(out.resolve("receipt.json"),canonical(Map.of("status","PASS","slots",2,"voters",5,"hiddenOriginalIndex",1,"runtimeEnabled",false),65536));
        }finally {
            Files.write(out.resolve("calls.json"),canonical(f.calls,8*1024*1024));
            Files.write(out.resolve("observations.json"),canonical(V53JournalApplicationTest.observations(f.observations),1024*1024));
        }
    }
}
