package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;

/** Only live typed owners can authorize a refreshed source acquisition. A
 * retained selector, source capsule or receipt value cannot implement this. */
sealed interface MembershipLearnerHead permits MembershipLearnerMaterialization.PreparedGeneration,
        MembershipLearnerMaterialization.CurrentHead {
    void check()throws IOException;
    MembershipLearnerRequest request()throws IOException;
    MembershipCapsule source()throws IOException;
    MembershipFormat.Decoded receipt()throws IOException;
    MembershipResources resources()throws IOException;
    void requireDisjoint(Path... paths)throws IOException;
}
