package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;

/** A failed pre-grant floor acquisition must neither delete originals nor
 * disguise corruption as a fresh-campaign opportunity. */
class V53MaintenanceCampaignTest {
    @TempDir Path temp;
    @Test void unavailableOriginalCopiesStopBeforeGrantAndPermitBoundedFreshWait()throws Exception {
        check(true);
    }
    @Test void arbitraryCopyFailureRemainsTerminalWithoutAuthorityMutation()throws Exception {
        check(false);
    }
    void check(boolean unavailable)throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network(3)) {
            n.activate();var owner=n.owners.getFirst();var resources=n.resources.getFirst();
            assertTrue(owner.publishedMaintenanceRequired());
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());
            var sent=new ArrayList<String>();var deadlines=new HashSet<Long>();long began=System.nanoTime();
            try(var driver=new MembershipActivationDriver(owner,n.endpoints.getFirst(),resources,n.bounds,(peer,request,kind,deadline)->{
                sent.add(request.kind());deadlines.add(deadline);
                return CompletableFuture.failedFuture(unavailable?new MembershipTransport.Failure(MembershipTransport.Reason.IO,"no original copy",null):new IOException("invalid original copy"));
            },List.of(),List.of(),temp.resolve("new-driver"),System::nanoTime,V53NativeDispatchTest.BUDGET,3)) {
                var error=assertThrows(Exception.class,()->driver.run(began));
                if(unavailable) {
                    assertEquals(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,assertInstanceOf(MembershipCampaignLost.class,error).reason);
                    var missing=assertInstanceOf(MembershipGenerationMaintenance.Unavailable.class,error.getCause());
                    var serving=assertThrows(MembershipCampaignLost.class,()->MembershipRoundDriver.campaignCall(()->{throw missing;}));
                    assertSame(missing,serving.getCause());assertEquals(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,serving.reason);
                    missing.addSuppressed(new IOException("receiving cleanup failed"));
                    assertSame(missing,assertThrows(MembershipGenerationMaintenance.Unavailable.class,()->MembershipRoundDriver.campaignCall(()->{throw missing;})));
                }
                else {assertInstanceOf(IOException.class,error);assertFalse(error instanceof MembershipCampaignLost);}
                assertEquals(0,driver.campaigns(),"no new durable ballot before a verified floor");
                assertFalse(sent.isEmpty());assertTrue(sent.stream().allMatch("STATUS_PROBE"::equals));
                assertEquals(Set.of(began+V53NativeDispatchTest.BUDGET),deadlines);
                assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            }
        }
    }
}
