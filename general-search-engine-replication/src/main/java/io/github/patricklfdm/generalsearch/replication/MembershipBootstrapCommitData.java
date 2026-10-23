package io.github.patricklfdm.generalsearch.replication;

import java.nio.file.Path;
import java.util.*;

/** Original transaction metadata plus the verified actual initial application.
 * Derivation never establishes durable admission or permits replica opening. */
final class MembershipBootstrapCommitData {
    static final List<String> STATES=MembershipBootstrapCommitMetadata.STATES;
    static final String JOURNAL=MembershipBootstrapCommitMetadata.JOURNAL,RECEIPT=MembershipBootstrapCommitMetadata.RECEIPT,
        PENDING=MembershipBootstrapCommitMetadata.PENDING,PREPARED=MembershipBootstrapCommitMetadata.PREPARED,
        SEAL=MembershipBootstrapCommitMetadata.SEAL,SEAL_PENDING=MembershipBootstrapCommitMetadata.SEAL_PENDING;
    final MembershipBootstrapPlanData plan;
    final MembershipBootstrapCommitMetadata metadata;
    final List<Path> targets;
    final List<MembershipIdentity> identities;
    final long completionBytes;
    MembershipBootstrapCommitData(MembershipBootstrapPlanData plan) {
        this.plan=Objects.requireNonNull(plan);metadata=new MembershipBootstrapCommitMetadata(new MembershipBootstrapPlanMetadata(plan.bytes()));
        targets=metadata.targets;identities=metadata.identities;completionBytes=metadata.completionBytes;
    }
    static byte[] container(int kind,Map<String,Object> value){return MembershipBootstrapCommitMetadata.container(kind,value);}
    Map<String,byte[]> payload(int i){return plan.seed.payloads(identities.get(i));}
    byte[] preparation(int i){return metadata.preparation(i);}byte[] seal(int i){return metadata.seal(i);}
    byte[] receipt(){return metadata.receipt();}byte[] row(int phase){return metadata.row(phase);}
    byte[] journal(int phase){return metadata.journal(phase);}
    MembershipBootstrapResult result(){return metadata.result();}
}
