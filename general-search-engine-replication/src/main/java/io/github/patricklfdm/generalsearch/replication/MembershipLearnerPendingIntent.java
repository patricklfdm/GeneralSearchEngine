package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;

/** Complete retained SEALED source plus the original pending INTENT exchange.
 * Force the matching new-side checkpoint end before issuing its acknowledgement.
 * It remains a nonserving learner: no election vote, selector or joint publication. */
final class MembershipLearnerPendingIntent implements AutoCloseable {
    private final MembershipLearnerDisposition retained;
    private MembershipLearnerPendingIntent(MembershipLearnerDisposition retained){this.retained=retained;}
    static Path directory(MembershipLearnerPlan plan){return MembershipLearnerDisposition.directory(plan,MembershipLearnerDisposition.Kind.PENDING_INTENT);}
    static MembershipLearnerPendingIntent install(MembershipLearnerProgress.PendingIntent original,MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerPendingIntent(MembershipLearnerDisposition.installPending(original,cut));
    }
    static MembershipLearnerPendingIntent resume(MembershipLearnerHead head,MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerPendingIntent(MembershipLearnerDisposition.resume(head,cut,MembershipLearnerDisposition.Kind.PENDING_INTENT));
    }
    MembershipCapsule source()throws IOException{return retained.pendingSource();}
    MembershipJoiningIntentMetadata originals()throws IOException{return retained.pendingOriginals();}
    MembershipAppliedEndFiles.Endorsement endorse()throws IOException{return retained.endorsePending();}
    MembershipLearnerCheckpointEndpoint listen(ReplicationBounds bounds,MembershipTransport.Events events,
            java.util.function.LongSupplier clock,long started,long budget)throws IOException {
        return retained.servePending(bounds,events,clock,started,budget);
    }
    @Override public void close()throws IOException{retained.close();}
}
