package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Complete missing compacted ancestry for one already fixed candidate source set.
 * No new source is substituted while proof is acquired; failure needs a fresh ballot.
 * The runtime owns this receiving lifetime through every selected installation. */
final class MembershipActivationAncestry implements AutoCloseable {
    record Resolution(List<MembershipSelection.Source> sources,List<MembershipSelection.Bridge> bridges) {
        Resolution {sources=List.copyOf(sources);bridges=List.copyOf(bridges);}
    }
    @FunctionalInterface interface Resolver {Resolution resolve(List<MembershipSelection.Source> sources)throws IOException;}
    static final class Failure extends IOException {
        private static final long serialVersionUID=1L;
        final MembershipIdentity source;
        Failure(MembershipIdentity source,IOException cause){super("activation original ancestry unavailable: "+source.nodeId().value(),cause);this.source=source;}
    }
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipSourcePull.Link link;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private final Path prefixDirectory;
    private final Map<String,MembershipSourceReceive> originals;
    private final List<MembershipSourcePull> pulls=new ArrayList<>();
    private MembershipSourceReceive prefix;
    private MembershipSourcePull ancestry;
    private boolean used,closed,ancestryComplete;

    MembershipActivationAncestry(MembershipGrantJournal owner,MembershipResources resources,ReplicationBounds bounds,
            MembershipSourcePull.Link link,MembershipSourcePull.Guard guard,LongSupplier clock,long started,long budget,
            Path prefixDirectory,Map<String,MembershipSourceReceive> originals) {
        require(budget>0 && budget<Long.MAX_VALUE/2 && originals.size()<=5,"activation ancestry bounds");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);
        this.link=Objects.requireNonNull(link);this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;this.prefixDirectory=Objects.requireNonNull(prefixDirectory);this.originals=Map.copyOf(originals);
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"activation ancestry closed/original deadline");
        guard.check();elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"activation ancestry closed/original deadline");
    }
    void recheck()throws IOException {check();if(prefix!=null)prefix.recheck();if(ancestryComplete)ancestry.ancestryBytes();check();}
    static MembershipSelection.Source longest(List<MembershipSelection.Source> sources) {
        require(sources.size()>=2 && sources.size()<=6,"activation ancestry source count");
        String proposer=(String)object(sources.getFirst().basis.value().get("ballot")).get("proposer");
        var longest=sources.stream().filter(s->s.owner.nodeId().value().equals(proposer)).findFirst().orElseThrow();
        for(var source:sources)if(number(source.capsule.context.cut.get("index"))>number(longest.capsule.context.cut.get("index")))longest=source;
        return longest;
    }
    static List<MembershipCapsule.Anchor> missing(MembershipSelection.Source longest,List<MembershipSelection.Source> sources) {
        var result=new ArrayList<MembershipCapsule.Anchor>();
        for(var source:sources) {
            longest.capsule.context.monotonicFrom(source.capsule.context);var lower=source.capsule.terminal();
            var existing=longest.capsule.anchor(number(lower.cut().get("index")));
            require(existing==null || existing.equals(lower),"conflicting proven capsule anchor");
            if(existing==null && !result.contains(lower))result.add(lower);
        }
        return List.copyOf(result);
    }
    Resolution resolve(List<MembershipSelection.Source> sources)throws IOException {
        require(!used,"activation ancestry single use");used=true;check();
        var longest=longest(sources);var missing=missing(longest,sources);
        if(missing.isEmpty())return new Resolution(sources,List.of());
        List<MembershipSelection.Bridge> available;
        if(longest.owner.equals(owner.activationIdentity())) {
            available=owner.activationAncestry(longest.basis);
            longest=longest.withVerifiedHistory(longest.capsule.retainingVerifiedAncestry(available));
        }else {
            var received=originals.get(longest.owner.nodeId().value());require(received!=null,"activation ancestry original receive missing");
            require(Arrays.equals(received.basis().bytes(),longest.basis.bytes()),"activation ancestry original grant changed");
            var hint=new MembershipDiscovery.Hint(longest.owner,longest.capsule.context.cut,false);
            try {
                var current=MembershipSourcePull.prefix(owner,hint,resources,bounds,link,this::check,clock,started,budget);pulls.add(current);
                prefix=current.fetchPrefix(prefixDirectory,received);
                var verified=current.verifiedPrefix();
                ancestry=MembershipSourcePull.prefix(owner,hint,resources,bounds,link,this::check,clock,started,budget);pulls.add(ancestry);
                var complete=ancestry.fetchAncestry(verified);ancestryComplete=true;available=ancestry.ancestry();
                var projected=complete.materialization(longest.capsule.packet,received.images(),available);
                longest=longest.withVerifiedHistory(projected);
            }catch(IOException error){throw new Failure(longest.owner,error);}
        }
        var needed=new ArrayList<MembershipSelection.Bridge>();
        for(var lower:missing) {
            var matches=available.stream().filter(b->b.statement.value().get("start").equals(lower.cut())).toList();
            require(matches.size()==1,"unavailable original compacted ancestry");var bridge=matches.getFirst();bridge.verify(longest.capsule,lower);needed.add(bridge);
        }
        var complete=new ArrayList<MembershipSelection.Source>();
        for(var source:sources)complete.add(source.owner.equals(longest.owner)?longest:source);
        recheck();return new Resolution(complete,needed);
    }
    @Override public void close()throws IOException {
        closed=true;IOException failure=null;
        for(var pull:pulls.reversed())try{pull.close();}catch(IOException|RuntimeException error){if(failure==null)failure=new IOException("activation ancestry cleanup",error);else failure.addSuppressed(error);}
        if(failure!=null)throw failure;
    }
}
