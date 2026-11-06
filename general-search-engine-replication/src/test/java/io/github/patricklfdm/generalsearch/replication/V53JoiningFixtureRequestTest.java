package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.object;

/** The direct duplicate-request fixture owns its real logical bytes as well as TCP copies. */
class V53JoiningFixtureRequestTest {
    @Test void directFixtureRequestIsChargedBeforeSubmissionAndReleasedAfterSuccessOrFailure()throws Exception {
        for(boolean failure:List.of(false,true))try(var f=new V53LearnerDiscoveryTest().new Fixture()) {
            var pool=new MembershipResources(MembershipResources.METADATA_LIMIT,512*MembershipResources.MIB,MembershipResources.QUEUE_LIMIT,32);
            var request=V53JoiningIntentExportTest.initial(f.request,f.peer,f.capsule.context.cut);
            MembershipSourcePull.Link link=(peer,original,kind,deadline)->{
                var row=pool.observations().changes().getLast();assertEquals("RESERVE",row.event());
                var charge=row.added().getFirst();assertTrue(charge.owner().startsWith("source-request-"+original.digest()+"-"));
                assertEquals(original.size(),charge.bytes());assertEquals(MembershipResources.Unit.CONTROL,charge.unit());
                return failure?CompletableFuture.failedFuture(V53LearnerDiscoveryTest.lost()):CompletableFuture.completedFuture(
                        V53LearnerDiscoveryTest.response(original,"SOURCE_OFFER",Map.of("id",object(original.value().get("payload")).get("id"),
                                "digest",f.fixture.source.rootHash,"kind","RECORD","bytes",(long)f.content.length)));
            };
            if(failure)assertThrows(ExecutionException.class,()->V53JoiningIntentExportTest.exchange(link,pool,f.peer,request,"SOURCE_OFFER"));
            else assertEquals("SOURCE_OFFER",V53JoiningIntentExportTest.exchange(link,pool,f.peer,request,"SOURCE_OFFER").kind());
            assertEquals(0,pool.usage().leases());assertEquals("RELEASE",pool.observations().changes().getLast().event());
        }
    }
}
