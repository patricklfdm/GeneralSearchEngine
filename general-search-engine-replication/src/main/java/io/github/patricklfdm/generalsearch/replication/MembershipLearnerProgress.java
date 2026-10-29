package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Live prepared-owner progress acquisition. Complete original bytes and ancestry
 * are verified before returning. This owner has no voter install, vote or delete API;
 * only an explicit certified-CANCEL transaction may retain these originals.
 * INTENT installation is a separate protocol boundary. */
final class MembershipLearnerProgress implements AutoCloseable {
    private final MembershipLearnerHead head;
    private final MembershipLearnerRequest request;
    private final Path cancellationDirectory;
    private final MembershipIdentity peer;
    private final MembershipResources resources;
    private final ReplicationBounds bounds;
    private final MembershipTransport.Events events;
    private final LongSupplier clock;
    private final long started,budget;
    private volatile boolean closed;
    private boolean used;
    private MembershipTransport transport;
    private MembershipLearnerDiscovery discovery;
    private MembershipSourcePull prefix,generation;
    private MembershipFloor.Copy result;

    MembershipLearnerProgress(MembershipLearnerHead head,MembershipIdentity peer,ReplicationBounds bounds,
            MembershipTransport.Events events,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"learner progress original budget");
        this.head=Objects.requireNonNull(head);head.check();MembershipLearnerCancellation.requireActive(head);
        if(head instanceof MembershipLearnerMaterialization.CurrentHead current)current.requireAvailable();
        cancellationDirectory=MembershipLearnerCancellation.directory(MembershipLearnerCancellation.store(head).summary());
        request=head.request();resources=head.resources();this.peer=Objects.requireNonNull(peer);
        require(!peer.equals(request.identity()) && request.change().target().contains(peer),"learner progress contact route");
        this.bounds=Objects.requireNonNull(bounds);this.events=Objects.requireNonNull(events);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;check();
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"learner progress closed/original deadline");head.check();MembershipLearnerCancellation.requireActive(cancellationDirectory);
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"learner progress closed/original deadline");
    }
    MembershipFloor.Copy fetch(Path scratch)throws IOException {
        head.requireDisjoint(scratch);AdmissionPaths.disjoint(List.of(scratch,request.replicaDirectory(),request.operationDirectory()));
        synchronized(this){check();require(!used,"learner progress single use");used=true;}
        try {
            var original=head.source();var root=decode(original.packet.objectBytes(original.context.recordRootDigest()),"records","ROOT");
            synchronized(this) {
                check();transport=MembershipTransport.learner(request,bounds,resources,events);
                discovery=new MembershipLearnerDiscovery(request,peer,resources,bounds,transport::exchange,this::check,clock,started,budget);
            }
            // ROOT comes from the original prepared owner. A terminal operation
            // cannot re-enroll through the active-reservation ROOT route.
            var hint=discovery.hint();check();transport.close();
            synchronized(this) {
                check();transport=MembershipTransport.learnerProgress(request,hint,bounds,resources,events);
                prefix=MembershipSourcePull.learnerProgress(request,root,hint,resources,bounds,transport::exchange,this::check,clock,started,budget);
                generation=MembershipSourcePull.learnerProgress(request,root,hint,resources,bounds,transport::exchange,this::check,clock,started,budget);
            }
            prefix.fetchPrefix(scratch);prefix.verifiedPrefix();var next=generation.fetchGeneration(prefix);check();
            MembershipLearnerSource.successor(original,next);check();
            synchronized(this){check();result=next;return next;}
        }catch(IOException|RuntimeException|Error error) {
            try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;
        }
    }
    MembershipFloor.Copy source()throws IOException {
        check();require(result!=null,"learner progress incomplete");prefix.verifiedPrefix();generation.ancestryManifest();result.check();check();return result;
    }
    MembershipLearnerCancellation retainCancellation(MembershipBallotAllocator.Cut cut)throws IOException {
        var copy=source();MembershipLearnerCancellation.cancellation(head,copy);
        var receiver=prefix.completeLearnerCancellationSource(copy,cut);check();
        return MembershipLearnerCancellation.install(head,receiver,copy,cut);
    }
    @Override public void close()throws IOException {
        MembershipLearnerDiscovery d;MembershipSourcePull p,g;MembershipTransport t;
        synchronized(this){closed=true;result=null;d=discovery;p=prefix;g=generation;t=transport;}
        MembershipLearnerSource.closeChildren(d,g,p,t);
    }
}
