package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One bounded recording per immutable prefix service. Prefix, ancestry and
 * generation traces share the same result, failure and original deadline. No
 * network wait holds the registry or journal monitor. Close cancels the round
 * before the transfer service drains any entry that may be waiting for it. */
final class MembershipLearnerRetentionServing implements AutoCloseable {
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final MembershipContext context;
    private final MembershipSourcePull.Link link;
    private final LongSupplier clock;
    private final long started,budget;
    private MembershipIdentity learner;
    private MembershipLearnerRetentionQuorum round;
    private MembershipResources.Lease metadata;
    private final CompletableFuture<MembershipLearnerRetentionQuorum.Recording> result=new CompletableFuture<>();
    private boolean closed,finished;

    MembershipLearnerRetentionServing(MembershipGrantJournal owner,MembershipContext context,MembershipResources resources,MembershipSourcePull.Link link,
            LongSupplier clock,long started,long budget) {
        this.owner=owner;this.context=context;this.resources=resources;this.link=Objects.requireNonNull(link);
        this.clock=clock;this.started=started;this.budget=budget;
    }
    private void time(){long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"learner serving original deadline/closed");}
    MembershipLearnerRetentionQuorum.Recording get(MembershipIdentity reader)throws IOException {
        boolean first=false;
        synchronized(this) {
            time();
            if(learner==null) {
                // Reserve before constructing the retained intent/result. A
                // failed constructor leaves no unaccounted registry entry.
                var lease=resources.reserve(MembershipResources.Unit.CONTROL,"learner-serving-"+UUID.randomUUID(),65536);
                try {
                    synchronized(owner) {
                        require(owner.activationContext().cut.equals(context.cut),"learner serving original cut changed");
                        round=new MembershipLearnerRetentionQuorum(owner,reader,owner.voting(resources).ballot,resources,link,clock,started,budget);
                    }
                    metadata=lease;learner=reader;first=true;
                }catch(IOException|RuntimeException|Error error){lease.close();throw error;}
            }
            require(learner.equals(reader),"learner serving changed original identity");
        }
        if(first) {
            try{result.complete(round.run());}
            catch(IOException|RuntimeException|Error error){result.completeExceptionally(error);throw error;}
            finally{synchronized(this){finished=true;if(closed)metadata.close();}}
        }
        try {
            long left; synchronized(this){time();left=budget-(clock.getAsLong()-started);}
            require(left>0,"learner serving original deadline/closed");
            var recording=result.get(left,TimeUnit.NANOSECONDS);recording.checkExport(owner,reader,resources);
            synchronized(this){time();}return recording;
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("learner serving interrupted",error);}
        catch(TimeoutException error){close();throw new IOException("learner serving original deadline",error);}
        catch(ExecutionException error) {
            if(error.getCause() instanceof IOException io)throw io;
            if(error.getCause() instanceof RuntimeException runtime)throw runtime;
            if(error.getCause() instanceof Error fatal)throw fatal;
            throw new IOException("learner serving recording failed",error.getCause());
        }
    }
    @Override public void close() {
        MembershipLearnerRetentionQuorum active;
        synchronized(this) {
            if(closed)return;closed=true;active=round;
            result.completeExceptionally(new IOException("learner serving closed"));
            if(finished && metadata!=null)metadata.close();
        }
        if(active!=null)active.close();
    }
}
