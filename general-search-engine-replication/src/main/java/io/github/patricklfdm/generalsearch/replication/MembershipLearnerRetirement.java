package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipBasisSources.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original decision permits only missing covered predecessors. It is not a
 * source capability: the live successor must authenticate its source and head
 * before forcing this decision and performing any deletion or lease release. */
final class MembershipLearnerRetirement {
    static final String FILE="retire.json";
    static final int MAXIMUM=4096;
    private final Path directory;
    private final Object directoryKey;
    private final FileIdentity marker,head;
    private MembershipLearnerRetirement(Path directory,byte[] bytes,byte[] headBytes)throws IOException {
        this.directory=directory;directoryKey=key(directory);
        marker=inspect(directory.resolve(FILE),bytes.length,hash(bytes));
        head=inspect(directory.resolve(MembershipLearnerSuccessor.HEAD),headBytes.length,hash(headBytes));
    }
    static byte[] bytes(MembershipLearnerAdmissionPlan plan,MembershipLearnerRetention retention)throws IOException {
        Path directory=MembershipLearnerSuccessor.directory(plan.summary()),head=directory.resolve(MembershipLearnerSuccessor.HEAD);
        byte[] bytes=AdmissionPaths.read(head,MembershipLearnerSuccessor.HEAD_MAXIMUM);
        return canonical(Map.of("schema","gse-v53-learner-retirement/1.3","plan",plan.summary().planDigest(),
                "retention",hash(retention.bytes()),"head",hash(bytes),"headKey",key(head).toString()),MAXIMUM);
    }
    static MembershipLearnerRetirement load(MembershipLearnerAdmissionPlan plan,MembershipLearnerRetention retention)throws IOException {
        Path directory=AdmissionPaths.safe(MembershipLearnerSuccessor.directory(plan.summary()));
        if(!Files.exists(directory.resolve(FILE),LinkOption.NOFOLLOW_LINKS))return null;
        byte[] bytes=AdmissionPaths.read(directory.resolve(FILE),MAXIMUM);
        require(Arrays.equals(bytes,bytes(plan,retention)),"learner retirement original decision differs or incomplete");
        require(!Files.exists(directory.resolve(MembershipLearnerSuccessor.HEAD_NEXT),LinkOption.NOFOLLOW_LINKS),"learner retirement redundant handoff");
        return new MembershipLearnerRetirement(directory,bytes,AdmissionPaths.read(directory.resolve(MembershipLearnerSuccessor.HEAD),MembershipLearnerSuccessor.HEAD_MAXIMUM));
    }
    void check()throws IOException {
        require(directoryKey.equals(key(directory))
                && marker.equals(inspect(directory.resolve(FILE),marker.bytes(),marker.digest()))
                && head.equals(inspect(directory.resolve(MembershipLearnerSuccessor.HEAD),head.bytes(),head.digest())),
                "learner retirement original identity changed");
    }
}
