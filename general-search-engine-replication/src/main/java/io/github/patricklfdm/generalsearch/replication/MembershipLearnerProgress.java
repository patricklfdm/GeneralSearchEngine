package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Live prepared-owner progress acquisition. Complete original bytes and ancestry
 * are verified before returning. This owner has no voter install, vote or delete API;
 * explicit certified CANCEL or matching INTENT transactions may retain these
 * originals. Subsequent voter installation is a separate protocol boundary. */
final class MembershipLearnerProgress implements AutoCloseable {
    private final MembershipLearnerHead head;
    private final MembershipLearnerDisposition.RetainedSource pending;
    private final MembershipLearnerRequest request;
    private final MembershipLearnerPlan terminalPlan;
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
    private MembershipTransport joiningTransport;
    private MembershipJoiningIntentPull joining;

    MembershipLearnerProgress(MembershipLearnerHead head,MembershipIdentity peer,ReplicationBounds bounds,
            MembershipTransport.Events events,LongSupplier clock,long started,long budget)throws IOException {
        this(head,null,peer,bounds,events,clock,started,budget);
    }
    /** This capability comes only from the force-before-SOURCE handoff. It
     * authorizes read-only published history acquisition, not generic admission. */
    MembershipLearnerProgress(MembershipLearnerDisposition.RetainedSource pending,MembershipIdentity peer,ReplicationBounds bounds,
            MembershipTransport.Events events,LongSupplier clock,long started,long budget)throws IOException {
        this(Objects.requireNonNull(pending).head(),pending,peer,bounds,events,clock,started,budget);
    }
    private MembershipLearnerProgress(MembershipLearnerHead head,MembershipLearnerDisposition.RetainedSource pending,
            MembershipIdentity peer,ReplicationBounds bounds,MembershipTransport.Events events,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"learner progress original budget");
        this.head=Objects.requireNonNull(head);this.pending=pending;head.check();
        if(pending==null) {
            MembershipLearnerCancellation.requireActive(head);
            if(head instanceof MembershipLearnerMaterialization.CurrentHead current)current.requireAvailable();
        }else {pending.requireAcquisition();require(pending.head()==head,"joining progress foreign head");}
        terminalPlan=MembershipLearnerCancellation.store(head).summary();
        request=head.request();resources=head.resources();this.peer=Objects.requireNonNull(peer);
        require(!peer.equals(request.identity()) && request.change().target().contains(peer),"learner progress contact route");
        this.bounds=Objects.requireNonNull(bounds);this.events=Objects.requireNonNull(events);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;check();
    }
    private void check()throws IOException {
        long elapsed=clock.getAsLong()-started;
        require(!closed && elapsed>=0 && elapsed<budget,"learner progress closed/original deadline");head.check();
        if(pending==null)MembershipLearnerCancellation.requireActive(terminalPlan);else pending.requireAcquisition();
        elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"learner progress closed/original deadline");
    }
    MembershipFloor.Copy fetch(Path scratch)throws IOException {
        if(pending!=null)pending.requireScratch(scratch);
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
            MembershipLearnerSource.successor(original,next);if(pending!=null)pending.matchPublished(next);check();
            synchronized(this){check();result=next;return next;}
        }catch(IOException|RuntimeException|Error error) {
            try{close();}catch(IOException|RuntimeException cleanup){error.addSuppressed(cleanup);}throw error;
        }
    }
    MembershipFloor.Copy source()throws IOException {
        check();require(result!=null,"learner progress incomplete");prefix.verifiedPrefix();generation.ancestryManifest();result.check();check();return result;
    }
    MembershipLearnerCancellation retainCancellation(MembershipBallotAllocator.Cut cut)throws IOException {
        require(pending==null,"joining published acquisition cannot become cancellation");
        var copy=source();MembershipLearnerCancellation.cancellation(head,copy);
        var receiver=prefix.completeLearnerCancellationSource(copy,cut);check();
        return MembershipLearnerCancellation.install(head,receiver,copy,cut);
    }
    MembershipLearnerIntent retainIntent(MembershipBallotAllocator.Cut cut)throws IOException {
        require(pending==null,"joining published source requires linked original retention");
        var copy=source();MembershipLearnerIntent.match(head,copy);
        var receiver=prefix.completeLearnerIntentSource(head,copy,cut);check();
        return MembershipLearnerIntent.install(head,receiver,copy,cut);
    }
    /** Read pending metadata against this exact complete SEALED transfer and
     * live typed owner. No received value is a durable joining witness. */
    synchronized MembershipJoiningIntentPull joiningMetadata()throws IOException {
        require(pending==null,"joining published acquisition cannot resample pending metadata");
        var copy=source();require(joiningTransport==null,"learner joining metadata single exchange");
        if(head instanceof MembershipLearnerMaterialization.CurrentHead current)current.requireAvailable();
        joiningTransport=MembershipTransport.learnerJoiningIntent(request,new MembershipDiscovery.Hint(peer,copy.capsule.context.cut,false),
                bounds,resources,events);
        try {
            joining=new MembershipJoiningIntentPull(request,peer,copy.capsule,head.receipt(),resources,bounds,joiningTransport::exchange,
                    ()->{source();head.check();if(head instanceof MembershipLearnerMaterialization.CurrentHead current)current.requireAvailable();},
                    clock,started,budget);
            return joining;
        }catch(IOException|RuntimeException|Error error){joiningTransport.close();throw error;}
    }
    /** Only this real complete source and dedicated authenticated contact can
     * supply pending receipt provenance. Decoded metadata alone cannot. */
    final class PendingIntent {
        private final MembershipFloor.Copy copy;
        private final MembershipJoiningIntentMetadata metadata;
        private PendingIntent()throws IOException {copy=MembershipLearnerProgress.this.source();require(joining!=null,"joining metadata exchange missing");metadata=joining.metadata();check();}
        void check()throws IOException {
            require(MembershipLearnerProgress.this.source()==copy && joining.metadata()==metadata,"joining original exchange changed");head.check();
            MembershipJoiningIntentMetadata.inspect(request,peer,copy.capsule,head.receipt(),metadata.bytes());
        }
        MembershipLearnerHead head()throws IOException{check();return head;}
        MembershipFloor.Copy source()throws IOException{check();return copy;}
        byte[] metadata()throws IOException{check();return metadata.bytes();}
        MembershipSourceReceive receiver(MembershipBallotAllocator.Cut cut)throws IOException {
            check();var receiver=prefix.completeLearnerPendingIntentSource(head,copy,cut);check();return receiver;
        }
    }
    MembershipLearnerPendingIntent retainPendingIntent(MembershipBallotAllocator.Cut cut)throws IOException {
        require(pending==null,"joining published acquisition cannot recreate pending retention");
        return MembershipLearnerPendingIntent.install(new PendingIntent(),cut);
    }
    @Override public void close()throws IOException {
        MembershipLearnerDiscovery d;MembershipSourcePull p,g;MembershipTransport t,jt;MembershipJoiningIntentPull j;
        synchronized(this){closed=true;result=null;d=discovery;p=prefix;g=generation;t=transport;jt=joiningTransport;j=joining;}
        MembershipLearnerSource.closeChildren(j,jt,d,g,p,t);
    }
}
