package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;

/** A retained source owner can prepare a nonvoting typed backup. This capability
 * is deliberately distinct from a selected current head. */
sealed interface MembershipLearnerImageSource permits MembershipLearnerSuccessor.View, MembershipLearnerSlot.View {
    MembershipCapsule source()throws IOException;
    MembershipLearnerStore store()throws IOException;
    byte[] originalImage(String digest,long size)throws IOException;
    Path typedDirectory()throws IOException;
    void requireTypedPaths(Path core,Path typed)throws IOException;
    void reserveTypedImage()throws IOException;
    void attachTyped(MembershipLearnerMaterialization<?> typed)throws IOException;
    void requireCurrentTyped(MembershipLearnerMaterialization<?> typed)throws IOException;
    void requireRefreshPaths(Path... paths)throws IOException;
}
