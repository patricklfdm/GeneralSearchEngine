package io.github.patricklfdm.generalsearch.replication;

import java.util.Map;
import java.util.UUID;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;

/** Local observation identities, never wire authority or durable state. The
 * nonce distinguishes allocations even when an exact request/session recurs. */
final class MembershipSourceResources {
    private MembershipSourceResources() {}
    static String export(String role,String originalDigest) {
        MembershipValidation.digest(originalDigest);
        return role+"-"+originalDigest+"-"+UUID.randomUUID();
    }
    static String request(String role,Decoded request) {
        return role+"-"+request.digest()+"-"+UUID.randomUUID();
    }
    static String session(String role,String root,MembershipIdentity source,MembershipIdentity reader,UUID trace) {
        String binding=hash(canonical(Map.of("root",root,"source",MembershipBootstrapSeed.identity(source),
                "reader",MembershipBootstrapSeed.identity(reader),"trace",trace.toString()),8192));
        return role+"-"+binding+"-"+UUID.randomUUID();
    }
}
