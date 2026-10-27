package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Retire one inactive generation only after acquiring complete original copies
 * from both governing majorities. Hints, control ACKs and caller hashes are never
 * floor authority. Source pins live through force/retirement/release. */
final class MembershipGenerationMaintenance implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.Voting original;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final Path scratch;
    private final LongSupplier clock;
    private final long started,budget;
    private final Set<MembershipSourcePull> pulls=new HashSet<>();
    private MembershipDiscovery discovery;
    private volatile boolean closed;
    private boolean used;
    MembershipGenerationMaintenance(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,Path scratch,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"native maintenance budget");this.owner=Objects.requireNonNull(owner);
        this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);this.link=Objects.requireNonNull(link);
        this.guard=Objects.requireNonNull(guard);this.scratch=Objects.requireNonNull(scratch);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;original=owner.voting(resources);check();
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"native maintenance closed/original deadline");
        guard.check();original.check();elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"native maintenance closed/original deadline");
    }
    private boolean quorum(Collection<String> voters) {
        for(String side:List.of("old","new")) {var members=MembershipContext.nodes(original.before.context.view,side);
            if(voters.stream().filter(members::contains).count()<=members.size()/2)return false;}return true;
    }
    private MembershipDiscovery.Hint discover(MembershipIdentity peer)throws IOException {
        var work=new MembershipDiscovery(owner,resources,bounds,link,this::check,clock,started,budget);
        synchronized(this){if(closed){work.close();throw new IOException("native maintenance closed");}discovery=work;}
        try(work){return work.query(peer);}finally{synchronized(this){if(discovery==work)discovery=null;}}
    }
    private MembershipSourcePull prefix(MembershipDiscovery.Hint hint)throws IOException {
        var work=MembershipSourcePull.prefix(owner,hint,resources,bounds,link,this::check,clock,started,budget);
        synchronized(this){if(!closed){pulls.add(work);return work;}}
        work.close();throw new IOException("native maintenance closed");
    }
    private void release(MembershipSourcePull work)throws IOException {
        if(work==null)return;try{work.close();}finally{synchronized(this){pulls.remove(work);}}
    }
    void run()throws IOException {
        synchronized(this){require(!used && !closed,"native maintenance single use/closed");used=true;}
        check();if(!owner.nativeGenerationMaintenanceRequired())return;
        var own=owner.floorCopyCurrent();var copies=new ArrayList<MembershipFloor.Copy>();copies.add(own);
        var voters=new TreeSet<String>();voters.add(own.owner.nodeId().value());
        for(String node:new TreeSet<>(original.before.context.voters())) {
            if(quorum(voters))break;if(voters.contains(node))continue;check();
            MembershipSourcePull source=null,generation=null;boolean retain=false;
            try {
                var hint=discover(original.before.context.identities.get(node));check();
                if(!hint.cut().equals(original.before.context.cut))continue;
                source=prefix(hint);source.fetchPrefix(scratch.resolve("source-"+UUID.randomUUID()));
                generation=prefix(hint);var copy=generation.fetchGeneration(source);check();
                require(copy.owner.equals(hint.peer()) && copy.capsule.terminal().equals(own.capsule.terminal()),"native maintenance exact original copy");
                copies.add(copy);voters.add(node);retain=true;
            }catch(MembershipTransport.Failure error) {
                if(error.reason!=MembershipTransport.Reason.IO && error.reason!=MembershipTransport.Reason.DEADLINE
                        && error.reason!=MembershipTransport.Reason.CAPACITY)throw error;check();
            }finally{if(!retain){try{release(generation);}finally{release(source);}}}
        }
        check();require(quorum(voters),"native generation maintenance quorum unavailable");
        owner.establishFloor(copies);check();
        // Only these complete original copies can rule out an earlier remote
        // possibility. A publication ACK or STATUS hint cannot narrow the ledger.
        for(var copy:copies){owner.retainPeerObservation(copy);check();}
        owner.retireInactive();check();owner.releaseFloor();check();
    }
    @Override public void close()throws IOException {
        List<MembershipSourcePull> closing;MembershipDiscovery query;
        synchronized(this){closed=true;closing=List.copyOf(pulls);query=discovery;discovery=null;}
        if(query!=null)query.close();IOException failure=null;
        for(var pull:closing)try{release(pull);}catch(IOException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        if(failure!=null)throw failure;
    }
}
