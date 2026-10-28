package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Own one complete native source acquisition before any learner admission.
 * No voter state, directories, preparation receipt or public readiness is created. */
final class MembershipLearnerSource implements AutoCloseable {
    private final MembershipLearnerRequest request;
    private final MembershipIdentity peer;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipTransport.Events events;
    private final MembershipSourcePull.Guard guard;
    private final LongSupplier clock;
    private final long started,budget;
    private volatile boolean closed;
    private boolean used;
    private MembershipTransport transport;
    private MembershipLearnerDiscovery discovery;
    private MembershipSourcePull prefix,generation;
    private MembershipFloor.Copy result;

    MembershipLearnerSource(MembershipLearnerRequest request,MembershipIdentity peer,MembershipResources resources,
            ReplicationBounds bounds,MembershipTransport.Events events,MembershipSourcePull.Guard guard,
            LongSupplier clock,long started,long budget) {
        require(budget>0 && budget<Long.MAX_VALUE/2,"learner source original budget");
        this.request=Objects.requireNonNull(request);this.peer=Objects.requireNonNull(peer);
        require(!peer.equals(request.identity()) && request.change().target().contains(peer),"learner source contact route");
        this.resources=Objects.requireNonNull(resources);this.bounds=Objects.requireNonNull(bounds);this.events=Objects.requireNonNull(events);
        this.guard=Objects.requireNonNull(guard);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"learner source closed/original deadline");guard.check();
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"learner source closed/original deadline");
    }
    private synchronized MembershipLearnerDiscovery query()throws IOException {
        check();discovery=new MembershipLearnerDiscovery(request,peer,resources,bounds,transport::exchange,this::check,clock,started,budget);return discovery;
    }
    MembershipFloor.Copy fetch(Path scratch)throws IOException {
        AdmissionPaths.disjoint(List.of(scratch,request.replicaDirectory(),request.operationDirectory()));
        synchronized(this){require(!used && !closed,"learner source single use");used=true;}
        try {
            synchronized(this){check();transport=MembershipTransport.learner(request,bounds,resources,events);}
            var root=query().fetch();var hint=query().hint();check();
            // Finish the contact transport before creating the source-only one.
            transport.close();
            synchronized(this) {
                check();transport=MembershipTransport.learnerPrefix(request,hint,bounds,resources,events);
                prefix=MembershipSourcePull.learner(request,root,hint,resources,bounds,transport::exchange,this::check,clock,started,budget);
                generation=MembershipSourcePull.learner(request,root,hint,resources,bounds,transport::exchange,this::check,clock,started,budget);
            }
            prefix.fetchPrefix(scratch);prefix.verifiedPrefix();var copy=generation.fetchGeneration(prefix);check();
            MembershipLearnerPrefixExport.originalReservation(copy.capsule.context,request,peer);
            synchronized(this){check();result=copy;return copy;}
        }catch(IOException|RuntimeException|Error error){try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;}
    }
    MembershipFloor.Copy source()throws IOException {
        check();require(result!=null,"learner source incomplete");prefix.verifiedPrefix();generation.ancestryManifest();result.check();check();return result;
    }
    /** Persist the exact reviewed plan before any learner authority directory.
     * It grants no readiness or votes; later apply must install these originals. */
    MembershipLearnerPlan plan(MembershipBallotAllocator.Cut cut)throws IOException {
        var plan=MembershipLearnerAdmissionPlan.create(request,source());
        try(var files=MembershipLearnerAdmissionFiles.create(plan,resources,cut,()->plan.checkOriginal(source()))) {
            return files.summary();
        }
    }
    @Override public void close()throws IOException {
        MembershipLearnerDiscovery d;MembershipSourcePull p,g;MembershipTransport t;
        synchronized(this){closed=true;result=null;d=discovery;p=prefix;g=generation;t=transport;}
        closeChildren(d,g,p,t);
    }
    /** A refused scratch cleanup must still close all network owners. The original
     * failure remains primary, and retained scratch can be inspected/retried. */
    static void closeChildren(AutoCloseable... children)throws IOException {
        Exception failure=null;
        for(var child:children)if(child!=null)try{child.close();}catch(Exception error) {
            if(failure==null)failure=error;else failure.addSuppressed(error);
        }
        if(failure instanceof IOException io)throw io;
        if(failure instanceof RuntimeException runtime)throw runtime;
        if(failure!=null)throw new IOException("learner source cleanup failed",failure);
    }
}
