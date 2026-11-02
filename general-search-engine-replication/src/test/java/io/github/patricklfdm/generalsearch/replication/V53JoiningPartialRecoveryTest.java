package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.V53SourceExchangeTest.BUDGET;

/** Conditional original custody with an explicit partial-file fixture. This
 * regression tests read admission only, never a complete native crash history. */
class V53JoiningPartialRecoveryTest {
    @TempDir Path temp;
    V53LearnerCancellationTest.Fixture partial(byte[] prefix)throws Exception {
        var h=new V53LearnerJoinedAdmissionTest();h.temp=temp;var f=h.fixture();
        try {
            try(var placement=h.place(f)) {
                var joined=h.join(placement,f,event->{});
                try(var retired=MembershipLearnerJoinedRetirement.retire(joined,f.local.captured,f.local.config,event->{});
                    var owner=MembershipGrantJournal.openJoined(retired,f.local.captured,f.local.config,event->{})) {
                    assertNotNull(owner.activationContext());
                }
            }
            Files.write(f.local.config.replicaDirectory().resolve(MembershipJoiningRetentionFiles.NEXT),prefix,StandardOpenOption.CREATE_NEW);
            return f;
        }catch(Exception|Error error){f.close();throw error;}
    }
    MembershipGrantJournal open(V53LearnerCancellationTest.Fixture f)throws Exception {
        return MembershipGrantJournal.reopenJoinedRetaining(f.local.summary,f.local.source.client,f.local.captured,f.local.config,event->{});
    }
    @Test void emptyOriginalCandidateCanReacquireButCannotGrantOrExposeReady()throws Exception {
        try(var f=partial(new byte[0]);var owner=open(f)) {
            var pool=f.local.source.client;var before=V53ReplayFilesTest.files(f.local.config.replicaDirectory());var usage=pool.usage();
            var preparation=owner.joiningRetentionPreparation(pool);preparation.check();
            var state=owner.discoveryState(pool);var context=state.context();
            var old=context.identities.get(MembershipContext.nodes(context.view,"old").getFirst());
            MembershipSourcePull.Link link=(peer,q,kind,deadline)->CompletableFuture.failedFuture(new AssertionError("no fetch required for admission checks"));
            try(var endpoint=new MembershipJoiningEndpoint<>(owner,pool,f.local.config.bounds(),link,temp.resolve("scratch"),()->0,0,BUDGET,f.local.captured,f.local.config.materialization());
                var read=MembershipSourcePull.prefix(owner,new MembershipDiscovery.Hint(old,context.cut,false),pool,f.local.config.bounds(),link,preparation::check,()->0,0,BUDGET);
                var discovery=new MembershipJoiningPreparationRendezvous(owner,pool,f.local.config.bounds(),link,preparation::check,()->0,0,BUDGET);
                var scan=new MembershipJoiningPreparationDiscovery(owner,pool,f.local.config.bounds(),link,preparation::check,()->0,0,BUDGET);
                var exported=owner.exportPrefix(MembershipContext.cutDigest(context.cut),state.ballot(),context.authority(),pool,()->0,0,BUDGET)) {
                assertFalse(exported.references().isEmpty());assertEquals(MembershipEndpointHandoff.State.READ_ONLY,endpoint.state());
                var status=MembershipActivation.frame("STATUS_PROBE",context,old,owner.activationIdentity(),state.ballot(),UUID.randomUUID(),1,Map.of("nonce",UUID.randomUUID().toString()));
                assertEquals(false,object(endpoint.handle(old,status).value().get("payload")).get("ready"));
                var higher=new TreeMap<String,Object>(state.ballot());higher.put("counter",99L);
                var request=MembershipActivation.frame("PREPARE",context,old,owner.activationIdentity(),higher,UUID.randomUUID(),1,Map.of("promise","ab".repeat(32)));
                assertThrows(IllegalArgumentException.class,()->endpoint.handle(old,request));
                assertEquals(state,owner.discoveryState(pool));
                assertThrows(IllegalArgumentException.class,endpoint::votingEndpoint);
                assertThrows(IllegalArgumentException.class,owner::activationCapsule);
                assertThrows(IllegalArgumentException.class,owner::activationContext);
                assertThrows(IllegalArgumentException.class,owner::beginActivation);
                assertThrows(IllegalArgumentException.class,()->owner.prepareCurrent(state.ballot()));
                assertThrows(IllegalArgumentException.class,owner::floorCopyCurrent);
                assertThrows(IllegalArgumentException.class,()->owner.joiningEndpointReady(pool));
                assertThrows(IllegalArgumentException.class,()->owner.openScratch(temp.resolve("forbidden"),MembershipScratch.Role.INCOMING,pool,event->{}));
                assertThrows(IllegalArgumentException.class,()->owner.joiningRetentionPreparation(new MembershipResources(512*MembershipResources.MIB)));
                assertFalse(Files.exists(temp.resolve("scratch")));assertFalse(Files.exists(temp.resolve("forbidden")));
            }
            preparation.check();assertEquals(usage,pool.usage());assertEquals(before,V53ReplayFilesTest.files(f.local.config.replicaDirectory()));
        }
    }
    @Test void originalPartialFramingRemainsReadOnlyAndMutationRevokesExistingPreparation()throws Exception {
        byte[] prefix=ByteBuffer.allocate(8).putInt(0x47534a52).putShort((short)1).putShort((short)3).array();
        try(var f=partial(prefix);var owner=open(f)) {
            var original=owner.joiningRetentionPreparation(f.local.source.client);original.check();
            Path file=f.local.config.replicaDirectory().resolve(MembershipJoiningRetentionFiles.NEXT);
            Files.write(file,new byte[]{1});
            try {
                assertThrows(Exception.class,original::check);assertThrows(Exception.class,owner::readOnlyCapsule);
                assertArrayEquals(new byte[]{1},Files.readAllBytes(file));
            }finally{Files.write(file,prefix);}
            original.check();Path saved=temp.resolve("actual-prefix");Files.move(file,saved);Files.write(file,prefix);
            try{assertThrows(Exception.class,original::check);assertThrows(Exception.class,owner::readOnlyCapsule);}
            finally{Files.delete(file);Files.move(saved,file);}
            original.check();
        }
    }
    @Test void missingOriginalDecisionNeverFallsBackToAnInstallationOnlyOwner()throws Exception {
        try(var f=partial(new byte[0])) {
            Path file=f.local.config.replicaDirectory().resolve(MembershipJoiningRetentionFiles.NEXT);Files.delete(file);
            assertThrows(IllegalArgumentException.class,()->open(f));assertFalse(Files.exists(file));
            assertEquals(0,f.local.source.client.usage().leases());
        }
    }
}
