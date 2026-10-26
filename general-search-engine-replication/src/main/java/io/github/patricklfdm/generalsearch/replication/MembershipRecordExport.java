package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One exact record from live forced storage, charged before copying. No disk pin or new ACK.
 * Every read rechecks the owner and continued physical retention; retirement ends the borrow. */
final class MembershipRecordExport implements MembershipTransferExport {
    static final Set<String> KINDS=Set.of("PROMISE","BASIS","SELECTED","ENTRY","ACCEPT","PROOF","CERTIFICATE","CHECKPOINT","CHECKPOINT_ACK");
    private final MembershipGrantJournal owner;
    private final MembershipContext context;
    private final MembershipIdentity identity;
    private final Map<String,Object> ballot;
    private final String kind,digest;
    private final byte[] bytes;
    private final MembershipResources.Lease lease;
    private final LongSupplier clock;
    private final long started,budget;
    private boolean closed;

    MembershipRecordExport(MembershipGrantJournal owner,MembershipContext context,MembershipIdentity identity,
            Map<String,Object> ballot,Decoded record,MembershipResources resources,LongSupplier clock,long started,long budget) {
        this.owner=owner;this.context=context;this.identity=identity;this.ballot=Map.copyOf(ballot);
        kind=record.kind();digest=record.digest();this.clock=clock;this.started=started;this.budget=budget;
        lease=resources.reserve(MembershipResources.Unit.CONTROL,"record-export-"+UUID.randomUUID(),record.size());
        try{bytes=record.bytes();}catch(RuntimeException|Error error){lease.close();throw error;}
    }
    String kind(){return kind;}
    String digest(){return digest;}
    boolean expired(){long elapsed=clock.getAsLong()-started;return closed || elapsed<0 || elapsed>=budget;}
    void revoke(){if(!closed){closed=true;lease.close();}}
    @Override public MembershipContext context(){return context;}
    @Override public MembershipIdentity identity(){return identity;}
    @Override public Map<String,Object> ballot(){return ballot;}
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
        synchronized(owner){owner.checkRecordExport(this);return Map.of(digest,new MembershipSourceExport.Content(digest,bytes.length,MembershipTransfer.Kind.RECORD));}
    }
    @Override public byte[] read(String reference,long offset,int maximum)throws IOException {
        synchronized(owner) {
            owner.checkRecordExport(this);require(digest.equals(reference) && offset>=0 && offset<bytes.length
                    && maximum>0 && maximum<=4*1024*1024,"record export reference/extent");
            int count=(int)Math.min(maximum,bytes.length-offset);byte[] result=Arrays.copyOfRange(bytes,Math.toIntExact(offset),Math.toIntExact(offset)+count);
            owner.checkRecordExport(this);return result;
        }
    }
    @Override public void close(){owner.releaseRecordExport(this);}
}
