package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Retire one inactive generation only after acquiring complete original copies
 * from both governing majorities. Hints, control ACKs and caller hashes are never
 * floor authority. Receiving ownership lives through durable floor/observations;
 * the floor then owns the complete copies through retirement/release. */
final class MembershipGenerationMaintenance implements AutoCloseable {
    /** A completed published-copy pass lacked exact original owners. No floor,
     * observation or retirement has been forced at this point. This type is
     * distinct from decoding, integrity, fencing and cleanup failures. */
    static final class Unavailable extends IOException {
        private static final long serialVersionUID=1L;
        private Unavailable(String message){super(message);}
    }
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.Voting original;
    private final MembershipGrantJournal.PublishedMaintenance published;
    private final MembershipContext context;
    private final Map<String,Object> ballot;
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
        this(owner,resources,bounds,link,guard,scratch,clock,started,budget,false);
    }
    static MembershipGenerationMaintenance beforeGrant(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,Path scratch,LongSupplier clock,long started,long budget)throws IOException {
        return new MembershipGenerationMaintenance(owner,resources,bounds,link,guard,scratch,clock,started,budget,true);
    }
    private MembershipGenerationMaintenance(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,Path scratch,LongSupplier clock,long started,long budget,boolean beforeGrant)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"native maintenance budget");this.owner=Objects.requireNonNull(owner);
        this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);this.link=Objects.requireNonNull(link);
        this.guard=Objects.requireNonNull(guard);this.scratch=Objects.requireNonNull(scratch);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;original=beforeGrant?null:owner.voting(resources);
        published=beforeGrant?owner.publishedMaintenance(resources):null;
        context=beforeGrant?published.context:original.before.context;ballot=beforeGrant?published.ballot:original.ballot;check();
    }
    private void check()throws IOException {
        if(closed)guard.check(); // Preserve a positive parent revocation, never infer one.
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"native maintenance closed/original deadline");
        guard.check();if(published==null)original.check();else published.check();elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"native maintenance closed/original deadline");
    }
    private boolean quorum(Collection<String> voters) {
        for(String side:List.of("old","new")) {var members=MembershipContext.nodes(context.view,side);
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
    static List<String> copyOrder(MembershipContext context,Set<String> joining) {
        return copyOrder(context,joining,Set.of());
    }
    static List<String> copyOrder(MembershipContext context,Set<String> joining,Set<String> installed) {
        require(joining.size()<=1 && context.voters().containsAll(joining),"maintenance joining identities");
        require(context.voters().containsAll(installed),"maintenance installed identities");
        return context.voters().stream().sorted(Comparator.<String,Boolean>comparing(n->!joining.contains(n))
                .thenComparing(n->!installed.contains(n))
                .thenComparing(Comparator.naturalOrder())).toList();
    }
    void run()throws IOException {
        synchronized(this){require(!used && !closed,"native maintenance single use/closed");used=true;}
        check();if(!(published==null?owner.nativeGenerationMaintenanceRequired():owner.publishedMaintenanceRequired()))return;
        var own=owner.floorCopyCurrent();var copies=new ArrayList<MembershipFloor.Copy>();copies.add(own);
        var receiving=new HashMap<String,List<MembershipSourcePull>>();
        var voters=new TreeSet<String>();voters.add(own.owner.nodeId().value());
        var joining=owner.maintenanceJoiningPeers();
        // The installed cohort has just acknowledged this selected cut. Prefer
        // it over unrelated voters, but still acquire every complete original
        // copy: neither that ACK nor this ordering is floor authority. A new
        // joining owner remains first; before-grant maintenance has no current
        // installed cohort and retains the ordinary known-voter order.
        var installed=new HashSet<String>();
        if(original!=null) {
            check();
            for(Object value:MembershipFormat.list(owner.originalSelection().orElseThrow().value().get("sources")))
                installed.add((String)MembershipFormat.object(value).get("voter"));
            check();
        }
        // The complete copies at this floor share the exact current application.
        // Borrow its live physical bytes instead of creating one receiving image
        // per remote copy in addition to the separately accounted floor images.
        try(var images=owner.exportPrefix(MembershipContext.cutDigest(context.cut),ballot,
                context.authority(),resources,clock,started,budget)) {
        for(String node:copyOrder(context,joining,installed)) {
            if(quorum(voters) && voters.containsAll(joining))break;if(voters.contains(node))continue;check();
            MembershipSourcePull source=null,generation=null;boolean retain=false;
            try {
                var hint=discover(context.identities.get(node));check();
                if(!hint.cut().equals(context.cut))continue;
                source=prefix(hint);
                try{source.fetchBorrowedPrefix(scratch.resolve("source-"+UUID.randomUUID()),images);}
                catch(MembershipSourcePull.MissingBorrowedImages missing) {
                    // Same terminal application need not mean identical historical
                    // image inventories. Only this completed packet-only probe may
                    // fall back; retain the original fence and overall deadline.
                    release(source);source=null;check();source=prefix(hint);
                    source.fetchPrefix(scratch.resolve("source-"+UUID.randomUUID()),images);
                }
                generation=prefix(hint);var copy=generation.fetchGeneration(source);check();
                require(copy.owner.equals(hint.peer()) && copy.capsule.terminal().equals(own.capsule.terminal()),"native maintenance exact original copy");
                copies.add(copy);voters.add(node);receiving.put(copy.generation.digest(),List.of(generation,source));retain=true;
            }catch(MembershipTransport.Failure error) {
                if(error.reason!=MembershipTransport.Reason.IO && error.reason!=MembershipTransport.Reason.DEADLINE
                        && error.reason!=MembershipTransport.Reason.CAPACITY)throw error;check();
            }finally{if(!retain){try{release(generation);}finally{release(source);}}}
        }
        check();
        if(published!=null && !quorum(voters))throw new Unavailable("native generation maintenance quorum unavailable");
        if(published!=null && !voters.containsAll(joining))throw new Unavailable("native generation maintenance joining copy unavailable");
        require(quorum(voters),"native generation maintenance quorum unavailable");
        require(voters.containsAll(joining),"native generation maintenance joining copy unavailable");
        owner.establishFloor(copies,copy->{
            // Only this exact complete replacement has been forced, including
            // directory parents. Delete its receiving scratch before reserving
            // another copy; never release an original source or image here.
            for(var work:receiving.getOrDefault(copy.generation.digest(),List.of()))release(work);
        });check();
        owner.reconcileMaintenancePeers();check();
        // Only these complete original copies can rule out an earlier remote
        // possibility. A publication ACK or STATUS hint cannot narrow the ledger.
        for(var copy:copies){owner.retainPeerObservation(copy);check();}
        // The forced floor now owns every exact copy, and the peer observations
        // are durable. The sequential handoff has already removed matching
        // receiving scratch; defensively drain anything still registered before
        // retirement reserves its saved original.
        List<MembershipSourcePull> received;
        synchronized(this){received=List.copyOf(pulls);}
        for(var work:received){release(work);check();}
        owner.retireInactive();check();
        if(published!=null)for(String source:owner.supersededPublishedSources(published)) {
            // The old physical source stays owned until its original retirement
            // decision and journal replacement are forced. A new campaign must
            // not accumulate another full image on top of obsolete sources.
            check();owner.retireSource(source);check();
        }
        owner.releaseFloor();check();
        }
    }
    @Override public void close()throws IOException {
        List<MembershipSourcePull> closing;MembershipDiscovery query;
        synchronized(this){closed=true;closing=List.copyOf(pulls);query=discovery;discovery=null;}
        if(query!=null)query.close();IOException failure=null;
        for(var pull:closing)try{release(pull);}catch(IOException error){if(failure==null)failure=error;else failure.addSuppressed(error);}
        if(failure!=null)throw failure;
    }
}
