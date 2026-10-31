package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.util.List;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test evidence is a bounded history, not one protocol message. Keep the exact
 * canonical array format while applying protocol encoding checks to each row. */
final class V53EvidenceArray {
    static final int WIRE_BYTES=64*1024*1024, EVENT_BYTES=32*1024*1024, HISTORY_ROWS=65536;
    private V53EvidenceArray() {}
    static byte[] encode(List<?> rows,int maximum) {
        require(maximum>=2,"evidence array byte capacity");
        require(rows.size()<=HISTORY_ROWS,"evidence array row capacity");
        var out=new ByteArrayOutputStream(Math.min(maximum,8192));out.write('[');boolean first=true;
        for(Object row:rows) {
            byte[] bytes=MembershipFormat.canonical(row,Math.min(maximum,16*1024*1024));
            int comma=first?0:1;
            require(bytes.length<=maximum-out.size()-comma-1,"evidence array byte capacity: rows="+rows.size()+", limit="+maximum+", retained="+out.size());
            if(!first)out.write(',');out.writeBytes(bytes);first=false;
        }
        out.write(']');return out.toByteArray();
    }
}
