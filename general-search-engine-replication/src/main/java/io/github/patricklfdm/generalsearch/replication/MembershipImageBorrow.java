package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;

/** Exact live physical images; a hash or caller byte map cannot implement this borrow. */
sealed interface MembershipImageBorrow permits MembershipSourceExport,MembershipSourceReceive {
    String imageRoot()throws IOException;
    boolean hasImage(String digest,long bytes)throws IOException;
    byte[] image(String digest,long bytes)throws IOException;
}
