package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Reclamation is not a grant prerequisite when only obsolete same-cut sources
 * occupy capacity. A failed floor acquisition cannot delete or waive them. */
class V53DeferredSourceMaintenanceTest {
    @TempDir Path temp;
    private void sources(V53NativeDispatchTest.Network n,int index)throws Exception {
        var owner=n.owners.get(index);var budget=n.resources.get(index);
        for(int i=0;i<2;i++)try(var campaign=new MembershipActivation(owner,budget,System::nanoTime,V53NativeDispatchTest.BUDGET)) {
            assertNotNull(campaign.ownSource());
        }
        assertTrue(owner.publishedMaintenanceRequired());assertFalse(owner.nativeGenerationMaintenanceRequired());
        assertEquals(2,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
    }
    @Test void missingOldCutCopiesRetainAllSourcesAndAllowANormallyReservedGrant()throws Exception {
        var helper=new V53NativeDispatchTest();helper.temp=temp;
        try(var n=helper.new Network()) {
            sources(n,0);var owner=n.owners.getFirst();var budget=n.resources.getFirst();
            var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());var usage=budget.usage();
            var requests=new ArrayList<String>();long began=System.nanoTime();
            try(var work=MembershipGenerationMaintenance.beforeGrant(owner,budget,n.bounds,(p,r,k,d)->{
                requests.add(r.kind());assertEquals(began+V53NativeDispatchTest.BUDGET,d);
                return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"old cut unavailable",null));
            },()->{},temp.resolve("maintenance"),System::nanoTime,began,V53NativeDispatchTest.BUDGET)) {work.run();}
            assertEquals(6,requests.size());assertTrue(requests.stream().allMatch("STATUS_PROBE"::equals));
            assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));
            assertEquals(usage,budget.usage());assertTrue(owner.governingFloor().isEmpty());
            try(var campaign=new MembershipActivation(owner,budget,System::nanoTime,V53NativeDispatchTest.BUDGET)) {
                assertNotNull(campaign.ownSource());assertEquals(3,budget.usage().counts().get(MembershipResources.Unit.SOURCE));
            }
        }
    }
    @Test void sourceOnlyWorkStillRejectsIntegrityFenceAndDeadlineFailures()throws Exception {
        for(String mode:List.of("integrity","fence","deadline")) {
            Path here=Files.createDirectory(temp.resolve(mode));var helper=new V53NativeDispatchTest();helper.temp=here;
            try(var n=helper.new Network()) {
                sources(n,0);var owner=n.owners.getFirst();var budget=n.resources.getFirst();
                var before=V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory());var usage=budget.usage();
                var clock=new java.util.concurrent.atomic.AtomicLong();
                try(var work=MembershipGenerationMaintenance.beforeGrant(owner,budget,n.bounds,(p,r,k,d)->{
                    if(mode.equals("integrity"))return CompletableFuture.failedFuture(new IOException("invalid original copy"));
                    if(mode.equals("deadline"))clock.set(V53NativeDispatchTest.BUDGET);
                    if(mode.equals("fence")) {
                        var higher=new TreeMap<>(object(owner.promised().orElseThrow().value().get("ballot")));
                        higher.put("counter",number(higher.get("counter"))+1);owner.observeCurrent(higher);
                    }
                    return CompletableFuture.failedFuture(new MembershipTransport.Failure(MembershipTransport.Reason.IO,"copy unavailable",null));
                },()->{},here.resolve("maintenance"),clock::get,0,V53NativeDispatchTest.BUDGET)) {
                    var error=assertThrows(Exception.class,work::run);
                    assertFalse(error instanceof MembershipGenerationMaintenance.Unavailable);
                    if(mode.equals("integrity"))assertEquals("invalid original copy",error.getMessage());
                }
                assertEquals(before,V53ReplayFilesTest.files(n.f.request.targets().getFirst().replicaDirectory()));assertEquals(usage,budget.usage());
            }
        }
    }
}
