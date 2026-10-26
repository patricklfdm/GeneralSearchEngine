package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One quorum recording round for an already authenticated same-view target.
 * Transport retries repeat exact frames. No measurement/client mutation retries,
 * automatic election, future publication target, or learner eligibility implied. */
final class MembershipRetentionQuorum implements AutoCloseable {
    @FunctionalInterface interface Dispatch<T> {T send()throws IOException;}
    final class Permit {
        private Permit() {}
        /** Queue only the exact target installation; the runtime owns the actual
         * transfer. The native ballot is checked immediately before dispatch. */
        <T> T dispatch(Dispatch<T> action)throws IOException {
            synchronized(owner){check();require(complete,"retention quorum incomplete");return action.send();}
        }
        Set<String> voters(){return Set.copyOf(acknowledged);}
        String intent(){return intent.digest;}
    }
    private record Reply(String node,Decoded response,Throwable failure) {}
    private final class Attempt implements AutoCloseable {
        final MembershipIdentity peer;
        final Decoded request;
        final MembershipExchange retry;
        final MembershipResources.Lease lease;
        CompletableFuture<Decoded> future;
        boolean cancelled;
        boolean exhausted;
        Attempt(MembershipIdentity peer,long sequence) {
            this.peer=peer;request=MembershipActivation.frame("RETENTION_INTENT",context,owner.activationIdentity(),peer,ballot,trace,sequence,intent.payload);
            retry=new MembershipExchange(request.digest(),started,budget);
            lease=resources.reserve(MembershipResources.Unit.CONTROL,"retention-"+UUID.randomUUID(),request.size());
        }
        void send()throws IOException {
            check();retry.attempt(request.digest(),clock.getAsLong());
            CompletableFuture<Decoded> next;
            try{next=Objects.requireNonNull(link.exchange(peer,request,"RETENTION_ACK",started+budget));}
            catch(RuntimeException failure){next=CompletableFuture.failedFuture(failure);}
            synchronized(this){future=next;if(cancelled || closed)next.cancel(true);}
            next.whenComplete((response,error)->replies.add(new Reply(peer.nodeId().value(),response,error)));
        }
        @Override public synchronized void close(){cancelled=true;if(future!=null && !future.isDone())future.cancel(true);lease.close();}
    }
    private final MembershipGrantJournal owner;
    private final MembershipResources resources;
    private final MembershipSourcePull.Link link;
    private final LongSupplier clock;
    private final long started,budget;
    private final MembershipContext context;
    private final Map<String,Object> ballot;
    private final MembershipRetentionIntent intent;
    private final UUID trace=UUID.randomUUID();
    private final SortedMap<String,Attempt> attempts=new ConcurrentSkipListMap<>();
    private final Set<String> acknowledged=new TreeSet<>();
    private final BlockingQueue<Reply> replies=new ArrayBlockingQueue<>(16);
    private volatile boolean closed;
    private final AtomicBoolean running=new AtomicBoolean();
    private volatile boolean complete;

    MembershipRetentionQuorum(MembershipGrantJournal owner,MembershipIdentity target,Map<String,Object> ballot,
            MembershipResources resources,MembershipSourcePull.Link link,LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"retention quorum budget");
        this.owner=Objects.requireNonNull(owner);this.resources=Objects.requireNonNull(resources);
        this.link=Objects.requireNonNull(link);this.clock=Objects.requireNonNull(clock);this.started=started;this.budget=budget;this.ballot=Map.copyOf(ballot);
        synchronized(owner){owner.checkRetentionResources(resources);context=owner.activationContext();intent=owner.peerRetentionIntent(target,ballot);}
        require(ballot.get("proposer").equals(owner.activationIdentity().nodeId().value()),"retention quorum proposer");
        time();
    }
    private void time(){long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"original retention deadline/closed");}
    private void check()throws IOException {time();owner.checkPeerRetentionDispatch(intent,ballot);time();}
    private boolean quorum(Collection<String> voters) {
        for(String side:List.of("old","new")) {
            var members=MembershipContext.nodes(context.view,side);
            if(voters.stream().filter(members::contains).count()<=members.size()/2)return false;
        }
        return true;
    }
    private static Throwable cause(Throwable error) {
        while((error instanceof CompletionException || error instanceof ExecutionException) && error.getCause()!=null)error=error.getCause();return error;
    }
    private boolean retryable(Throwable error) {
        return error instanceof MembershipTransport.Failure failure
                && (failure.reason==MembershipTransport.Reason.IO || failure.reason==MembershipTransport.Reason.DEADLINE);
    }
    private void acknowledge(MembershipIdentity peer,Decoded request,Decoded response) {
        MembershipWire.correlated(request,response,"RETENTION_ACK");MembershipWire.envelope(response,context.root,peer,owner.activationIdentity());
        require(response.kind().equals("RETENTION_ACK"),"retention acknowledgement rejected");var payload=object(response.value().get("payload"));
        require(payload.get("intent").equals(intent.digest),"retention acknowledgement changed intent");
        require(number(payload.get("revision"))<=MembershipBallotAllocator.MAX,"retention acknowledgement revision capacity");
        MembershipValidation.digest((String)payload.get("ledger"));acknowledged.add(peer.nodeId().value());
    }
    Permit run()throws IOException {
        require(!complete && !closed && running.compareAndSet(false,true),"retention quorum already used");
        try {
            time();var local=owner.activationIdentity();
            var request=MembershipActivation.frame("RETENTION_INTENT",context,local,local,ballot,trace,1,intent.payload);
            var response=owner.recordPeerRetention(local,request);acknowledge(local,request,response);check();
            long sequence=1;
            for(String node:new TreeSet<>(context.voters()))if(!node.equals(local.nodeId().value())) {
                var attempt=new Attempt(context.identities.get(node),++sequence);attempts.put(node,attempt);attempt.send();
            }
            while(!quorum(acknowledged)) {
                check();var possible=new HashSet<>(acknowledged);
                attempts.forEach((node,a)->{if(!a.exhausted)possible.add(node);});
                require(quorum(possible),"retention quorum unavailable");
                long left=budget-(clock.getAsLong()-started);Reply reply;
                try{reply=replies.poll(left,TimeUnit.NANOSECONDS);}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("retention quorum interrupted",error);}
                require(reply!=null,"original retention deadline/closed");check();var attempt=attempts.get(reply.node);
                require(attempt!=null && !attempt.exhausted && !acknowledged.contains(reply.node),"unexpected retention completion");
                if(reply.failure!=null) {
                    var error=cause(reply.failure);
                    if(retryable(error) && attempt.retry.attempts()<3){attempt.send();continue;}
                    if(error instanceof MembershipTransport.Failure failure && failure.reason!=MembershipTransport.Reason.PROTOCOL) {attempt.exhausted=true;attempt.close();continue;}
                    if(error instanceof IOException io)throw io;
                    if(error instanceof RuntimeException runtime)throw runtime;
                    throw new IOException("retention quorum peer failed",error);
                }
                var answer=reply.response;MembershipWire.correlated(attempt.request,answer,"RETENTION_ACK");
                if(answer.kind().equals("REJECT")) {
                    var promised=object(object(answer.value().get("payload")).get("promised"));context.ballot(promised,true);
                    if(MembershipContext.compareBallot(promised,ballot)>0){owner.observeCurrent(promised);check();}
                    attempt.exhausted=true;attempt.close();continue;
                }
                acknowledge(attempt.peer,attempt.request,answer);attempt.retry.complete(attempt.request.digest(),clock.getAsLong());attempt.close();
            }
            check();complete=true;return new Permit();
        } finally {for(var attempt:attempts.values())attempt.close();}
    }
    @Override public void close(){closed=true;for(var attempt:attempts.values())attempt.close();replies.offer(new Reply(null,null,null));}
}
