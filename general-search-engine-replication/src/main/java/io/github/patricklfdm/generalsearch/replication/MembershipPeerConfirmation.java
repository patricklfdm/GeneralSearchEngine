package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Original generation manifest retained after a complete forced-copy observation.
 * Decoding alone proves neither receipt nor force. Native observation accepts only
 * Floor.Copy; discharge additionally requires original selected-source provenance. */
final class MembershipPeerConfirmation {
    private final Decoded generation;
    final MembershipCapsule.Anchor endpoint;
    private MembershipPeerConfirmation(Decoded generation) {
        require(generation.family().equals("records") && generation.kind().equals("GENERATION"),"peer confirmation original generation");
        this.generation=generation;var value=generation.value();
        endpoint=new MembershipCapsule.Anchor(object(value.get("cut")),(String)value.get("catalog"),(String)value.get("application"));
    }
    static MembershipPeerConfirmation observed(MembershipFloor.Copy copy) {
        copy.check();var result=new MembershipPeerConfirmation(copy.generation);
        result.binding(copy.capsule.context.root,copy.owner);require(result.endpoint.equals(copy.capsule.terminal()),"peer confirmation original endpoint");return result;
    }
    static MembershipPeerConfirmation decodeValue(Object value) {
        require(value instanceof String,"peer confirmation encoding");String text=(String)value;
        require(text.length()<=32768,"peer confirmation ledger capacity");byte[] bytes=Base64.getDecoder().decode(text);
        require(Base64.getEncoder().encodeToString(bytes).equals(text),"peer confirmation canonical base64");
        return new MembershipPeerConfirmation(decode(bytes,"records","GENERATION"));
    }
    String value(){return Base64.getEncoder().encodeToString(generation.bytes());}
    String digest(){return generation.digest();}
    void binding(String root,MembershipIdentity peer) {
        require(generation.value().get("root").equals(root) && generation.value().get("node").equals(peer.nodeId().value()),"peer confirmation root/identity");
    }
}
