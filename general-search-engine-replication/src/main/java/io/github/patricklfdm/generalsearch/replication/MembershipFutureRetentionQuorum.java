package io.github.patricklfdm.generalsearch.replication;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.LongSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** Governing voters force their own proof of one unpublished target. This result
 * is a live internal prerequisite, not an application ACK, installation receipt,
 * durable quorum certificate, or completed publication/dispatch. */
final class MembershipFutureRetentionQuorum implements AutoCloseable {
    final class Recorded {
        private Recorded() {}
        void check()throws IOException {synchronized(owner){live();require(complete,"future recording quorum incomplete");}}
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
        boolean stopped,exhausted;
        Attempt(MembershipIdentity peer,long sequence) {
            this.peer=peer;request=MembershipActivation.frame("FUTURE_RETENTION_INTENT",context,owner.activationIdentity(),peer,ballot,trace,sequence,intent.payload);
            retry=new MembershipExchange(request.digest(),started,budget);
            lease=resources.reserve(MembershipResources.Unit.CONTROL,"future-intent-"+UUID.randomUUID(),request.size());
        }
        void send()throws IOException {
            live();retry.attempt(request.digest(),clock.getAsLong());CompletableFuture<Decoded> next;
            try{next=Objects.requireNonNull(link.exchange(peer,request,"FUTURE_RETENTION_ACK",started+budget));}
            catch(RuntimeException error){next=CompletableFuture.failedFuture(error);}
            synchronized(this){future=next;if(stopped || closed)next.cancel(true);}
            next.whenComplete((response,error)->replies.offer(new Reply(peer.nodeId().value(),response,error)));
        }
        @Override public synchronized void close(){stopped=true;if(future!=null && !future.isDone())future.cancel(true);lease.close();}
    }
    private final MembershipGrantJournal owner;
    private final MembershipGrantJournal.PendingPublication target;
    private final MembershipResources resources;
    private final MembershipSourcePull.Link link;
    private final MembershipContext context;
    private final Map<String,Object> ballot;
    private final MembershipFutureRetentionIntent intent;
    private final LongSupplier clock;
    private final long started,budget;
    private final UUID trace=UUID.randomUUID();
    private final SortedMap<String,Attempt> attempts=new ConcurrentSkipListMap<>();
    private final Set<String> acknowledged=new TreeSet<>();
    private final BlockingQueue<Reply> replies=new ArrayBlockingQueue<>(16);
    private final AtomicBoolean running=new AtomicBoolean();
    private volatile boolean closed,complete;
    MembershipFutureRetentionQuorum(MembershipGrantJournal owner,MembershipIdentity peer,Map<String,Object> ballot,
            MembershipGrantJournal.PendingPublication target,MembershipResources resources,MembershipSourcePull.Link link,
            LongSupplier clock,long started,long budget)throws IOException {
        require(budget>0 && budget<Long.MAX_VALUE/2,"future quorum budget");this.owner=Objects.requireNonNull(owner);this.target=Objects.requireNonNull(target);
        this.resources=Objects.requireNonNull(resources);this.link=Objects.requireNonNull(link);this.clock=Objects.requireNonNull(clock);
        this.started=started;this.budget=budget;this.ballot=Map.copyOf(ballot);
        synchronized(owner){owner.checkRetentionResources(resources);context=owner.activationContext();intent=owner.futureRetentionIntent(peer,ballot,target);}
        require(ballot.get("proposer").equals(owner.activationIdentity().nodeId().value()),"future quorum proposer");time();
    }
    private void time(){long elapsed=clock.getAsLong()-started;require(!closed && elapsed>=0 && elapsed<budget,"original future quorum deadline/closed");}
    private void live()throws IOException {time();owner.checkFutureRetentionRecording(intent,ballot,target);time();}
    private boolean quorum(Collection<String> voters) {
        for(String side:List.of("old","new")){var members=MembershipContext.nodes(context.view,side);if(voters.stream().filter(members::contains).count()<=members.size()/2)return false;}return true;
    }
    private static Throwable cause(Throwable error){while((error instanceof CompletionException || error instanceof ExecutionException) && error.getCause()!=null)error=error.getCause();return error;}
    private static boolean retryable(Throwable error){return error instanceof MembershipTransport.Failure f && (f.reason==MembershipTransport.Reason.IO || f.reason==MembershipTransport.Reason.DEADLINE);}
    private void acknowledge(MembershipIdentity peer,Decoded request,Decoded response) {
        MembershipWire.correlated(request,response,"FUTURE_RETENTION_ACK");MembershipWire.envelope(response,context.root,peer,owner.activationIdentity());
        require(response.kind().equals("FUTURE_RETENTION_ACK"),"future acknowledgement rejected");var payload=object(response.value().get("payload"));
        require(payload.get("intent").equals(intent.digest) && Set.of("FUTURE","CURRENT").contains(payload.get("storage")),"future acknowledgement changed intent/store");
        require(number(payload.get("revision"))<=MembershipBallotAllocator.MAX,"future acknowledgement revision capacity");
        MembershipValidation.digest((String)payload.get("digest"));require(acknowledged.add(peer.nodeId().value()),"duplicate future quorum voter");
    }
    Recorded record()throws IOException {
        require(!complete && !closed && running.compareAndSet(false,true),"future quorum already used");
        try {
            time();var local=owner.activationIdentity();
            var request=MembershipActivation.frame("FUTURE_RETENTION_INTENT",context,local,local,ballot,trace,1,intent.payload);
            acknowledge(local,request,owner.recordFutureRetention(local,request));live();long sequence=1;
            for(String node:new TreeSet<>(context.voters()))if(!node.equals(local.nodeId().value())) {
                var attempt=new Attempt(context.identities.get(node),++sequence);attempts.put(node,attempt);attempt.send();
            }
            while(!quorum(acknowledged)) {
                live();var possible=new HashSet<>(acknowledged);attempts.forEach((n,a)->{if(!a.exhausted)possible.add(n);});
                require(quorum(possible),"future retention quorum unavailable");Reply reply;
                try{reply=replies.poll(budget-(clock.getAsLong()-started),TimeUnit.NANOSECONDS);}
                catch(InterruptedException error){Thread.currentThread().interrupt();throw new IOException("future quorum interrupted",error);}
                require(reply!=null,"original future quorum deadline/closed");live();var attempt=attempts.get(reply.node);
                require(attempt!=null && !attempt.exhausted && !acknowledged.contains(reply.node),"unexpected future completion");
                if(reply.failure!=null) {
                    var error=cause(reply.failure);
                    if(retryable(error) && attempt.retry.attempts()<3){attempt.send();continue;}
                    if(error instanceof MembershipTransport.Failure f && f.reason!=MembershipTransport.Reason.PROTOCOL){attempt.exhausted=true;attempt.close();continue;}
                    if(error instanceof IOException io)throw io;if(error instanceof RuntimeException runtime)throw runtime;throw new IOException("future quorum peer failed",error);
                }
                MembershipWire.correlated(attempt.request,reply.response,"FUTURE_RETENTION_ACK");
                if(reply.response.kind().equals("REJECT")) {
                    var promised=object(object(reply.response.value().get("payload")).get("promised"));context.ballot(promised,true);
                    if(MembershipContext.compareBallot(promised,ballot)>0){owner.observeCurrent(promised);live();}
                    attempt.exhausted=true;attempt.close();continue;
                }
                acknowledge(attempt.peer,attempt.request,reply.response);attempt.retry.complete(attempt.request.digest(),clock.getAsLong());attempt.close();
            }
            live();complete=true;return new Recorded();
        }finally{for(var attempt:attempts.values())attempt.close();}
    }
    @Override public void close(){closed=true;for(var attempt:attempts.values())attempt.close();replies.offer(new Reply(null,null,null));}
}
