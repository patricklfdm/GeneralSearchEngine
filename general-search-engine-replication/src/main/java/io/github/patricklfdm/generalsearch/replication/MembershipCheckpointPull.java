package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Obtain an original compacted-ancestry proof from actual retained checkpoint
 * owners. A previously verified higher capsule and exact lower anchor are inputs;
 * this does not bootstrap historical capsule authority or perform cross-view adoption.
 * The runtime serializes fetch/use, supplies its live fence, and owns this borrow. */
final class MembershipCheckpointPull implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipCapsule higher;
    private final MembershipCapsule.Anchor lower;
    private final MembershipIdentity local;
    private final Map<String,Object> ballot;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final List<MembershipSourcePull> pulls=new ArrayList<>();
    private final List<MembershipRecordExport> exports=new ArrayList<>();
    private volatile boolean closed;
    private boolean used;
    private MembershipSelection.Bridge result;

    MembershipCheckpointPull(MembershipGrantJournal owner,MembershipCapsule higher,MembershipCapsule.Anchor lower,
            Map<String,Object> ballot,MembershipResources resources,ReplicationBounds bounds,MembershipSourcePull.Link link,
            MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"checkpoint pull time budget");
        this.owner=Objects.requireNonNull(owner);this.higher=Objects.requireNonNull(higher);this.lower=Objects.requireNonNull(lower);
        local=owner.activationIdentity();require(local.equals(higher.context.identities.get(local.nodeId().value())),"checkpoint pull local identity");
        higher.context.ballot(ballot,true);this.ballot=Map.copyOf(ballot);this.resources=Objects.requireNonNull(resources);
        this.bounds=Objects.requireNonNull(bounds);this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);
        this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"checkpoint pull closed/original deadline");guard.check();
        // The optional runtime guard cannot substitute for this storage owner's
        // root/view/ballot fence, including a higher promise observed during I/O.
        owner.checkActivationBallot(higher.context.authority(),ballot);
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"checkpoint pull closed/original deadline");
    }
    private MembershipSourcePull remote(MembershipIdentity peer)throws IOException {
        synchronized(this) {
            check();var pull=new MembershipSourcePull(higher,local,peer,ballot,UUID.randomUUID(),resources,bounds,link,this::check,clock,started,budget);
            pulls.add(pull);return pull;
        }
    }
    private Decoded local(Decoded expected)throws IOException {
        MembershipRecordExport export;
        synchronized(this) {
            check();export=owner.exportRecord(expected.digest(),expected.kind(),ballot,clock,started,budget);exports.add(export);
        }
        check();require(export.context().root.equals(higher.context.root) && export.context().authority().equals(higher.context.authority()),"checkpoint pull local authority");
        byte[] bytes=export.read(expected.digest(),0,4*1024*1024);
        require(Arrays.equals(bytes,expected.bytes()),"checkpoint pull local original bytes");check();return decode(bytes,"records",expected.kind());
    }
    /** Hints select references only; no supplied Owned or packet possession can count.
     * Every listed endorsement must be obtained, and the final set must be a quorum. */
    MembershipSelection.Bridge fetch(MembershipIdentity statementSource,Decoded statement,List<Decoded> acknowledgements)throws IOException {
        synchronized(this){require(!used && !closed,"checkpoint pull single use");used=true;}
        try {
            check();var hints=new MembershipSelection.Bridge(statement,acknowledgements,Set.of());hints.verifyEndpoints(higher,lower);
            require(statementSource.equals(higher.context.identities.get(statementSource.nodeId().value())),"checkpoint statement source identity");
            var voters=new ArrayList<String>();
            for(var ack:hints.acknowledgements) {
                String voter=(String)ack.value().get("voter");var peer=higher.context.identities.get(voter);
                require(peer!=null,"checkpoint ACK unknown owner");MembershipSourcePull.checkpointAcknowledgement(higher.context,peer,statement,ack);voters.add(voter);
            }
            orderedNodes(voters);quorum(object(object(statement.value().get("end")).get("view")),voters);
            Decoded original=statementSource.equals(local)?local(statement):remote(statementSource).fetchRecord(statement.digest(),"CHECKPOINT",value->{
                require(Arrays.equals(statement.bytes(),value.bytes()),"checkpoint original statement bytes");
            });
            var acks=new ArrayList<Decoded>();var owned=new HashSet<Owned>();
            for(var ack:hints.acknowledgements) {
                check();var peer=higher.context.identities.get((String)ack.value().get("voter"));
                if(peer.equals(local)) {
                    var actual=local(ack);MembershipSourcePull.checkpointAcknowledgement(higher.context,local,original,actual);acks.add(actual);
                    owned.add(new Owned(local.nodeId().value(),local.storageId(),actual.digest(),cutDigest(object(original.value().get("end")))));
                }else {
                    var receipt=remote(peer).fetchCheckpointAcknowledgement(original,ack);acks.add(receipt.acknowledgement());owned.add(receipt.owned());
                }
            }
            var complete=new MembershipSelection.Bridge(original,acks,owned);complete.verify(higher,lower);
            synchronized(this){check();result=complete;return result;}
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    MembershipSelection.Bridge bridge()throws IOException {
        check();require(result!=null,"checkpoint pull incomplete");for(var export:exports)export.references();check();return result;
    }
    @Override public void close()throws IOException {
        List<MembershipSourcePull> receiving;List<MembershipRecordExport> sending;
        synchronized(this){closed=true;result=null;receiving=List.copyOf(pulls);sending=List.copyOf(exports);}
        IOException failure=null;
        for(var pull:receiving)try{pull.close();}catch(IOException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        for(var export:sending)export.close();
        if(failure!=null)throw failure;
    }
}
