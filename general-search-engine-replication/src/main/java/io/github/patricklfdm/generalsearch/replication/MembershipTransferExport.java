package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;

/** Live, bounded, read-only content authority. Possession is not an installation or vote ACK. */
interface MembershipTransferExport extends AutoCloseable {
    MembershipContext context();
    MembershipIdentity identity();
    Map<String,Object> ballot();
    default void request(MembershipIdentity reader,MembershipFormat.Decoded request,UUID session) {
        context().wire(request,reader,identity(),ballot(),session,MembershipFormat.number(request.value().get("sequence")));
    }
    Map<String,MembershipSourceExport.Content> references() throws IOException;
    byte[] read(String digest,long offset,int maximum) throws IOException;
    @Override void close();
}
