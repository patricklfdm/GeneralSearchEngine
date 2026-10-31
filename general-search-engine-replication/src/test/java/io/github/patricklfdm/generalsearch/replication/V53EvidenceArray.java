package io.github.patricklfdm.generalsearch.replication;

import java.io.ByteArrayOutputStream;
import java.util.List;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Test evidence is a bounded history, not one protocol message. Keep the exact
 * canonical array format while applying protocol encoding checks to each row. */
final class V53EvidenceArray {
    private V53EvidenceArray() {}
    static byte[] encode(List<?> rows,int maximum) {
        require(maximum>=2,"evidence array byte capacity");
        var out=new ByteArrayOutputStream(Math.min(maximum,8192));out.write('[');boolean first=true;
        for(Object row:rows) {
            byte[] bytes=MembershipFormat.canonical(row,maximum);
            int comma=first?0:1;
            require(bytes.length<=maximum-out.size()-comma-1,"evidence array byte capacity");
            if(!first)out.write(',');out.writeBytes(bytes);first=false;
        }
        out.write(']');return out.toByteArray();
    }
}
