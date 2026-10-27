package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Accounted copy of this native owner's pending payload or original phase
 * receipt. A copied ACCEPT/PROOF in a capsule cannot create this exporter. */
final class MembershipVoteExport implements MembershipTransferExport {
    private final MembershipGrantJournal owner;
    final MembershipGrantJournal.Voting voting;
    final String reference,phase,record;
    private final byte[] bytes;
    private final String digest;
    private final MembershipResources.Lease lease;
    private final LongSupplier clock;
    private final long started,budget;
    private boolean closed;
    MembershipVoteExport(MembershipGrantJournal owner,MembershipGrantJournal.Voting voting,String reference,String phase,
            String record,int size,java.util.function.Supplier<byte[]> copy,MembershipResources resources,LongSupplier clock,long started,long budget) {
        this.owner=owner;this.voting=voting;this.reference=reference;this.phase=phase;this.record=record;
        this.clock=clock;this.started=started;this.budget=budget;
        lease=resources.reserve(MembershipResources.Unit.CONTROL,"vote-export-"+UUID.randomUUID(),size);
        try{bytes=copy.get();digest=MembershipFormat.hash(bytes);require(bytes.length==size
                && (digest.equals(reference) || MembershipVoteReceipt.reference(bytes).equals(reference)),"original vote export bytes");}
        catch(RuntimeException|Error error){lease.close();throw error;}
    }
    boolean expired(){long elapsed=clock.getAsLong()-started;return closed || elapsed<0 || elapsed>=budget;}
    void revoke(){if(!closed){closed=true;lease.close();}}
    @Override public MembershipContext context(){return voting.before.context;}
    @Override public MembershipIdentity identity(){return owner.activationIdentity();}
    @Override public Map<String,Object> ballot(){return voting.ballot;}
    @Override public Map<String,MembershipSourceExport.Content> references()throws IOException {
        synchronized(owner){owner.checkVoteExport(this);return Map.of(reference,new MembershipSourceExport.Content(digest,bytes.length,MembershipTransfer.Kind.RECORD));}
    }
    @Override public byte[] read(String digest,long offset,int maximum)throws IOException {
        synchronized(owner){owner.checkVoteExport(this);require(this.digest.equals(digest) && offset>=0 && offset<bytes.length
                && maximum>0 && maximum<=4*1024*1024,"vote export extent");
            int from=Math.toIntExact(offset);byte[] result=Arrays.copyOfRange(bytes,from,from+(int)Math.min(maximum,bytes.length-offset));
            owner.checkVoteExport(this);return result;}
    }
    @Override public void close(){owner.releaseVoteExport(this);}
}
