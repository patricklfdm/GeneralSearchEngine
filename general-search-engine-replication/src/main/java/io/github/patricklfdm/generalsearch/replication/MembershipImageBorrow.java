package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;

/** Exact live physical images; a hash or caller byte map cannot implement this borrow. */
sealed interface MembershipImageBorrow permits MembershipSourceExport,MembershipSourceReceive,MembershipPrefixExport {
    String imageRoot()throws IOException;
    boolean hasImage(String digest,long bytes)throws IOException;
    byte[] image(String digest,long bytes)throws IOException;
    /** Validate the live physical original without requiring a materialized copy.
     * Owners may specialize only when their check already inspects all bytes and
     * identities. The retained-source fallback still reads and hashes the image. */
    default void checkImage(String digest,long bytes)throws IOException {image(digest,bytes);}
}
