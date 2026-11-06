package io.github.patricklfdm.generalsearch.replication;

import java.util.*;

/** Optional bounded, process-local observations. They confer no storage authority.
 * Called only under the resource monitor; performs no I/O or external callback. */
final class MembershipResourceObservations {
    static final int MAXIMUM = 262144;
    record Charge(MembershipResources.Unit unit,String owner,long bytes,String claimSource) {}
    record Change(long sequence,String event,List<Charge> removed,List<Charge> added,MembershipResources.Usage usage) {}
    record Snapshot(long metadataLimit,long stagingLimit,long queueLimit,long transitions,boolean truncated,boolean failed,
                    List<Change> changes,MembershipResources.Usage current) {}
    record Checkpoint(long sequence,boolean complete,MembershipResources.Usage usage) {}
    record Move(Charge before,Charge after) {}
    record Transfer(long resourceSequence,List<Move> moves) {}
    record Transfers(long transitions,boolean truncated,boolean failed,List<Transfer> rows) {}
    private record Key(MembershipResources.Unit unit,String owner) {}
    private final int maximum;
    private final long metadataLimit,stagingLimit,queueLimit;
    private final List<Change> changes=new ArrayList<>();
    private final List<Transfer> transfers=new ArrayList<>();
    private Map<Key,Charge> prior=Map.of();
    private long transitions;
    private boolean truncated,failed;

    MembershipResourceObservations(int maximum,long metadataLimit,long stagingLimit,long queueLimit) {
        MembershipValidation.require(maximum>0 && maximum<=MAXIMUM,"resource observation bound");
        this.maximum=maximum;this.metadataLimit=metadataLimit;this.stagingLimit=stagingLimit;this.queueLimit=queueLimit;
    }
    void record(String event,List<Charge> charges,MembershipResources.Usage usage) {
        long sequence=transitions++;
        if(changes.size()==maximum){truncated=true;return;}
        var current=new HashMap<Key,Charge>();for(var charge:charges)current.put(new Key(charge.unit,charge.owner),charge);
        MembershipValidation.require(current.size()==charges.size(),"resource observation duplicate key");
        var removed=new ArrayList<Charge>();var added=new ArrayList<Charge>();
        prior.forEach((key,value)->{if(!value.equals(current.get(key)))removed.add(value);});
        current.forEach((key,value)->{if(!value.equals(prior.get(key)))added.add(value);});
        var order=Comparator.comparing((Charge c)->c.unit.name()).thenComparing(Charge::owner);
        removed.sort(order);added.sort(order);
        changes.add(new Change(sequence,event,List.copyOf(removed),List.copyOf(added),usage));prior=current;
    }
    boolean accepting(){return !truncated && !failed;}
    void transfer(List<Move> moves) {
        // One bounded mapping for an already recorded atomic switch. Equal-byte
        // charges in the delta alone cannot identify which handle succeeded which.
        MembershipValidation.require(accepting() && !changes.isEmpty() &&
                changes.getLast().event.equals("TRANSFER") && !moves.isEmpty() && moves.size()<=32 &&
                transfers.size()<maximum,"resource transfer observation bound/order");
        transfers.add(new Transfer(changes.getLast().sequence,List.copyOf(moves)));
    }
    Transfers transfers(){return new Transfers(transitions,truncated,failed,List.copyOf(transfers));}
    void skipped(){transitions++;}
    void failed(){failed=true;}
    Checkpoint checkpoint(MembershipResources.Usage usage) {
        return new Checkpoint(transitions-1,!truncated && !failed,usage);
    }
    Snapshot snapshot(MembershipResources.Usage usage) {
        return new Snapshot(metadataLimit,stagingLimit,queueLimit,transitions,truncated,failed,List.copyOf(changes),usage);
    }
}
