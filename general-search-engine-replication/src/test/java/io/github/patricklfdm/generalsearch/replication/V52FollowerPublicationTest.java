package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticProtocol.Kind.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;
import java.nio.file.Path;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Real authority stores, deterministic opaque application port; no public query oracle claim. */
class V52FollowerPublicationTest {
    @TempDir Path root;

    @Test void acceptedOnlySuffixNeverPublishesAndProofStillNeedsApplicationCompletion() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.node(2).enableReplicaReads();group.elect(1);group.node(2).tick(group.now);group.pump();
            assertEquals(1,group.node(2).view().publishedIndex());assertEquals(FOLLOWER,group.node(2).view().state());
            group.loss=m->m.response()&&m.kind()==ACCEPT;
            group.node(1).submit(71,1,new byte[]{42},group.now);group.pump();group.node(2).tick(group.now);group.pump();
            assertEquals(1,group.node(2).view().provenIndex());assertEquals(1,group.node(2).view().publishedIndex());
            var acceptance=group.dropped.getLast();
            group.loss=m->m.response()&&m.kind()==PROOF;group.deliver(acceptance);group.pump();
            assertEquals(2,group.node(2).view().provenIndex());assertEquals(1,group.node(2).view().publishedIndex());
            group.holdPublication=true;group.node(2).tick(group.now);group.pump();
            assertEquals(1,group.held.size());assertTrue(((AutomaticProtocol.Publish)group.held.getFirst().getValue()).local());
            assertEquals(1,group.node(2).view().publishedIndex());assertTrue(group.outcomes.isEmpty());
            group.holdPublication=false;group.releaseApplications();
            assertEquals(2,group.node(2).view().publishedIndex());assertEquals(FOLLOWER,group.node(2).view().state());
            assertTrue(group.outcomes.isEmpty(),"local publication cannot acknowledge the originating write");
        }
    }

    @Test void snapshotInstallationRemainsNonReadableUntilTheApplicationPublicationCompletes() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.node(3).enableReplicaReads();group.elect(1);group.submit(1,72,new byte[]{19});
            var published=group.publications.getLast();var snapshot=decode(unbase(published.get("snapshot")),"SNAPSHOT");
            var ballot=decode(unbase(published.get("ballot")),"PROMISE");
            group.node(3).rejoin(ballot,snapshot);
            assertEquals(RECOVERING,group.node(3).view().state());assertEquals(0,group.node(3).view().publishedIndex());
            group.holdReconstruction=true;group.node(3).tick(group.now);group.pump();
            assertEquals(RECOVERING,group.node(3).view().state());assertEquals(1,group.held.size());
            group.holdReconstruction=false;group.holdPublication=true;group.releaseApplications();
            assertEquals(RECOVERING,group.node(3).view().state());assertEquals(0,group.node(3).view().publishedIndex());
            group.holdPublication=false;group.releaseApplications();
            assertEquals(FOLLOWER,group.node(3).view().state());assertEquals(2,group.node(3).view().publishedIndex());
        }
    }

    @Test void higherPromiseDoesNotInvalidateACommittedLocalCutOrActivateLeadership() throws Exception {
        try(var group=new V51ProtocolFixture(root)) {
            group.node(2).enableReplicaReads();group.elect(1);group.holdPublication=true;
            group.node(2).tick(group.now);group.pump();assertEquals(1,group.held.size());
            var higher=decode(V51StorageFixture.promise(group.manifest,4),"PROMISE");
            group.node(2).receive(new AutomaticProtocol.Message(500,PREPARE,"node-3","node-2",higher,false,true,null,null),group.now);
            group.pump();assertEquals(4,group.node(2).view().promisedEpoch());
            group.holdPublication=false;group.releaseApplications();
            assertEquals(1,group.node(2).view().publishedIndex());assertEquals(FOLLOWER,group.node(2).view().state());
            assertEquals(4,group.node(2).view().promisedEpoch());assertTrue(group.outcomes.isEmpty());
        }
    }
}
