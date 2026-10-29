package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.Map;

/** Certified cancellation facade; existing bytes, paths and cut names remain unchanged. */
final class MembershipLearnerCancellation implements AutoCloseable {
    static final String PLAN=MembershipLearnerDisposition.PLAN,NEXT=MembershipLearnerDisposition.NEXT,SOURCE=MembershipLearnerDisposition.SOURCE;
    static final int MAXIMUM=MembershipLearnerDisposition.MAXIMUM;
    private final MembershipLearnerDisposition retained;
    private MembershipLearnerCancellation(MembershipLearnerDisposition retained){this.retained=retained;}
    static Path directory(MembershipLearnerPlan plan){return MembershipLearnerDisposition.directory(plan,MembershipLearnerDisposition.Kind.CANCEL);}
    static MembershipLearnerStore store(MembershipLearnerHead head)throws IOException{return MembershipLearnerDisposition.store(head);}
    static void requireActive(MembershipLearnerHead head)throws IOException{store(head).requireActive();}
    static void requireActive(MembershipLearnerPlan plan){MembershipLearnerDisposition.requireActive(plan);}
    static void requireActive(Path path){MembershipLearnerDisposition.requireAbsent(path,MembershipLearnerDisposition.Kind.CANCEL);}
    static boolean present(MembershipLearnerPlan plan){return Files.exists(AdmissionPaths.safe(directory(plan)),LinkOption.NOFOLLOW_LINKS);}
    static Map<String,Object> cancellation(MembershipLearnerHead head,MembershipFloor.Copy copy)throws IOException {
        return MembershipLearnerDisposition.cancellation(head,copy);
    }
    static MembershipLearnerCancellation install(MembershipLearnerHead head,MembershipSourceReceive receiver,MembershipFloor.Copy copy,
            MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerCancellation(MembershipLearnerDisposition.install(head,receiver,copy,cut,MembershipLearnerDisposition.Kind.CANCEL));
    }
    static MembershipLearnerCancellation resume(MembershipLearnerHead head,MembershipBallotAllocator.Cut cut)throws IOException {
        return new MembershipLearnerCancellation(MembershipLearnerDisposition.resume(head,cut,MembershipLearnerDisposition.Kind.CANCEL));
    }
    Map<String,Object> result()throws IOException{return retained.result();}
    boolean closed(){return retained.closed();}
    @Override public void close()throws IOException{retained.close();}
}
