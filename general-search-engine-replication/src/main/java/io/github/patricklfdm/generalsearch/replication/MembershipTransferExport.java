package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.Map;
import java.util.List;
import java.util.UUID;

/** Live, bounded, read-only content authority. Possession is not an installation or vote ACK. */
interface MembershipTransferExport extends AutoCloseable {
    MembershipContext context();
    MembershipIdentity identity();
    Map<String,Object> ballot();
    /** Exact CONTROL handles released by close, including nested borrows. Never
     * include the shared publication, journal or generation that serves bytes.
     * Observation only: handles remain identifiable after owner revocation. */
    List<MembershipResources.Lease> closeReservations();
    static List<MembershipResources.Lease> ownedWithBorrow(MembershipResources.Lease owned,MembershipTransferExport borrow) {
        var result=new java.util.ArrayList<MembershipResources.Lease>();result.add(owned);result.addAll(borrow.closeReservations());return List.copyOf(result);
    }
    default void request(MembershipIdentity reader,MembershipFormat.Decoded request,UUID session) {
        context().wire(request,reader,identity(),ballot(),session,MembershipFormat.number(request.value().get("sequence")));
    }
    Map<String,MembershipSourceExport.Content> references() throws IOException;
    byte[] read(String digest,long offset,int maximum) throws IOException;
    @Override void close();
}
