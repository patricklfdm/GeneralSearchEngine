package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Canonical reference for an original owner's phased vote. Deriving these bytes
 * is not an observation; only the native owner or a completed original-owner
 * transfer may attest them. This is the existing witness hash preimage. */
final class MembershipVoteReceipt {
    private MembershipVoteReceipt() {}
    static String reference(byte[] receipt) {
        // A plain payload hash may never select an attestation. Offer binds the
        // separate receipt digest, so a payload equal to this lookup preimage
        // cannot satisfy a receipt request either.
        return hash(canonical(Map.of("schema","gse-v53-vote-observation/1.3","receipt",hash(receipt)),2048));
    }
    static byte[] bytes(MembershipContext context,MembershipIdentity voter,Decoded record) {
        require(record.family().equals("records") && Set.of("ACCEPT","PROOF").contains(record.kind()),"vote receipt phase");
        var value=record.value();
        var view=object(context.cut.get("view"));String node=voter.nodeId().value();
        require(voter.equals(context.identities.get(node)) && (MembershipContext.nodes(view,"old").contains(node)
                || MembershipContext.nodes(view,"new").contains(node)),"vote receipt eligible original owner");
        require(value.get("root").equals(context.root) && value.get("authority").equals(context.authority())
                && number(value.get("index"))==number(context.cut.get("index"))+1,"vote receipt current next slot");
        context.ballot(value.get("ballot"),true);
        return canonical(Map.of("root",context.root,"voter",voter.nodeId().value(),"incarnation",voter.storageId().toString(),
                "phase",record.kind(),"record",record.digest()),2048);
    }
}
