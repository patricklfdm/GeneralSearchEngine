package io.github.patricklfdm.generalsearch.replication;

import java.nio.ByteBuffer;
import java.util.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Frozen 1.3 framing and exchange correlation; it grants no voting authority. */
final class MembershipWire {
    private MembershipWire() {}
    static String kind(byte[] header) {
        require(header.length>=HEADER,"truncated wire header");int id=Short.toUnsignedInt(ByteBuffer.wrap(header).getShort(8));
        for(var row:object(CATALOG.get("wire")).entrySet())if(number(object(row.getValue()).get("id"))==id)return row.getKey();
        throw new IllegalArgumentException("unknown wire kind");
    }
    static int bodyLength(byte[] header,int maximum) {
        require(maximum>=HEADER && maximum<=FRAME,"wire frame bound");
        int size=MembershipFormat.header(header,"wire",kind(header));require(size<=maximum-HEADER,"caller wire frame bound");return size;
    }
    static Decoded decode(byte[] bytes,int maximum) {
        int size=bodyLength(bytes,maximum);require(bytes.length==HEADER+size,"wire frame extent");
        return MembershipFormat.decode(bytes,"wire",kind(bytes));
    }
    static void envelope(Decoded frame,String root,MembershipIdentity sender,MembershipIdentity recipient) {
        require(frame.family().equals("wire") && frame.value().get("root").equals(root)
                && identity(object(frame.value().get("sender"))).equals(sender)
                && identity(object(frame.value().get("recipient"))).equals(recipient),"wire root/permanent identities");
    }
    static void correlated(Decoded request,Decoded response,String expectedKind) {
        require(object(CATALOG.get("wire")).containsKey(expectedKind),"unknown response kind");
        require(response.kind().equals(expectedKind) || response.kind().equals("REJECT"),"unexpected response kind");
        var before=request.value();var after=response.value();
        for(String field:List.of("root","view","ballot","trace","sequence"))
            require(before.get(field).equals(after.get(field)),"wire response correlation: "+field);
        require(before.get("sender").equals(after.get("recipient")) && before.get("recipient").equals(after.get("sender")),"wire response identity correlation");
    }
}
