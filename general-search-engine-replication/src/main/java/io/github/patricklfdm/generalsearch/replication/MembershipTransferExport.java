package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Map;

/** Live, bounded, read-only content authority. Possession is not an installation or vote ACK. */
interface MembershipTransferExport extends AutoCloseable {
    MembershipContext context();
    MembershipIdentity identity();
    Map<String,Object> ballot();
    Map<String,MembershipSourceExport.Content> references() throws IOException;
    byte[] read(String digest,long offset,int maximum) throws IOException;
    @Override void close();
}
