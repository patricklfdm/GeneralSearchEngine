package io.github.patricklfdm.generalsearch.replication;

import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Current-view liveness observation, never a grant, copied floor or read lease.
 * Authentication precedes the volatile higher-ballot fence. The advertised cut
 * and activated flag cannot replace original prefix acquisition or readiness. */
final class MembershipHeartbeat {
    private MembershipHeartbeat() {}

    static MembershipContext incoming(MembershipContext context,MembershipIdentity local,
            MembershipIdentity sender,Decoded request) {
        MembershipActivation.incoming(context,local,sender,request,"HEARTBEAT");
        require(!sender.equals(local),"heartbeat requires remote proposer");
        var advertised=object(object(request.value().get("payload")).get("cut"));
        require(viewDigest(context.root,object(advertised.get("view"))).equals(context.authority()),
                "heartbeat advertised view differs; discover original prefix");
        return context;
    }

    static Decoded answer(MembershipContext context,MembershipIdentity local,MembershipIdentity sender,Decoded request) {
        incoming(context,local,sender,request);
        return MembershipActivation.frame("HEARTBEAT_ACK",context,local,sender,object(request.value().get("ballot")),
                UUID.fromString((String)request.value().get("trace")),number(request.value().get("sequence")),
                Map.of("cut",context.cut));
    }
}
