package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.*;

/** Conditional original joint authority, not native joining/installation proof.
 * The actual sampler must use both sides and cannot turn contact into READY. */
class V53JointHeartbeatTest {
    @TempDir Path temp;
    @Test void oldSideOrNewSideMinorityCannotBecomeJointContact()throws Exception {
        sample(4,"ADD",Set.of("node-1","node-2","node-6"),false);
        sample(5,"REMOVE",Set.of("node-1","node-2","node-5"),false);
    }
    @Test void sharedMajoritiesNeedNotBeAMajorityOfTheUnion()throws Exception {
        sample(5,"REPLACE",Set.of("node-1","node-2","node-3"),true);
    }
    @Test void everyJointProfileUsesItsExactVoterUnionAndRetainsOriginalBytes()throws Exception {
        for(var profile:V53SelectionTest.PROFILES)sample(profile.getKey(),profile.getValue(),null,true);
    }
    private void sample(int size,String kind,Set<String> responding,boolean succeeds)throws Exception {
        var fixture=new V53CurrentGenerationFixture(size,new V53CapsuleFixture(size,kind,6));
        Path directory=temp.resolve(UUID.randomUUID().toString());fixture.provision(directory);var pool=resources();
        try(var owner=MembershipGrantJournal.openGenerations(directory,fixture.root(),V53DeclarationsTest.node(1),pool,fixture::verify,e->{})) {
            var state=owner.discoveryState(pool);var context=state.context();var before=V53ReplayFilesTest.files(directory);var usage=pool.usage();
            var requests=new ArrayList<MembershipFormat.Decoded>();
            try(var sample=new MembershipHeartbeatRound(owner,pool,bounds(),(peer,request,k,deadline)->{
                requests.add(request);assertEquals(BUDGET,deadline);
                if(responding!=null && !responding.contains(peer.nodeId().value()))return CompletableFuture.failedFuture(
                    new MembershipTransport.Failure(MembershipTransport.Reason.CAPACITY,"conditional absent contact",null));
                return CompletableFuture.completedFuture(MembershipHeartbeat.answer(context,peer,owner.activationIdentity(),request));
            },()->owner.checkActivationBallot(context.authority(),state.ballot()),()->0L,0,BUDGET)) {
                if(succeeds) {
                    var result=sample.run();context.quorum(result.responding());
                    if(responding!=null)assertEquals(responding,result.responding());
                }else assertEquals(MembershipCampaignLost.Reason.CONTACT_UNAVAILABLE,
                    assertThrows(MembershipCampaignLost.class,sample::run).reason);
            }
            assertEquals(context.voters().size()-1,requests.size());
            assertEquals(before,V53ReplayFilesTest.files(directory));assertEquals(usage,pool.usage());
            assertTrue(owner.originalSelection().isEmpty(),"conditional sampler must not create an installed selection");
        }
        assertEquals(0,pool.usage().leases());
    }
}
