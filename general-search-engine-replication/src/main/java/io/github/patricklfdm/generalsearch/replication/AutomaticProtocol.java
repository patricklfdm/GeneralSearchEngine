package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationState.*;

import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import java.util.*;
import java.util.function.LongSupplier;
import java.util.function.Supplier;

/**
 * Automatic authority transition kernel. No socket, application callback or future
 * completion runs under its monitor. A driver drains bounded actions and returns
 * their completions. Messages here are assembled internal values, not wire 1.2 frames.
 */
final class AutomaticProtocol implements AutoCloseable {
    enum Kind { PREPARE, INSTALL, ACCEPT, PROOF, HEARTBEAT }
    record Pulse(long sequence, boolean activated, long stage, long bytes) { }
    record Message(long id, Kind kind, String sender, String recipient, Record ballot,
                   boolean response, boolean accepted, Object payload, Record promised) { }
    sealed interface Action permits Send, Reconstruct, Publish, Completed { }
    record Send(Message message) implements Action { }
    record Reconstruct(long id, AutomaticStore.Replay replay) implements Action { }
    record Publish(long id, Record ballot, Record snapshot) implements Action { }
    record Completed(long request, long index, AutomaticReplicationException.Reason reason,
                     AutomaticReplicationException.Outcome outcome) implements Action { }
    record View(AutomaticReplicationState state, long promisedEpoch, long observedEpoch,
                int provenIndex, int publishedIndex, int pendingExchanges, boolean applicationPending) { }
    private static final int MAX_ACTIONS=32;
    private static final class Pending {
        final Message message; final long deadline;
        int attempts=1; long retryAt=Long.MAX_VALUE;
        Pending(Message message,long deadline) { this.message=message;this.deadline=deadline; }
    }
    private static final class Operation {
        final Record entry; final long request, deadline; final boolean campaign;
        String ownReceipt; Record proof; boolean issued;
        Operation(Record entry,long request,long deadline,boolean campaign) {
            this.entry=entry;this.request=request;this.deadline=deadline;this.campaign=campaign;
        }
    }
    private final AutomaticStore store;
    private final Record manifest;
    private final String local;
    private final List<String> peers;
    private final java.util.function.BiConsumer<String,Map<String,Object>> observer;
    private final ReplicationBounds bounds;
    private final AutomaticLeadershipPolicy policy;
    private final LongSupplier randomness;
    private final Supplier<UUID> incarnations;
    private final ArrayDeque<Action> actions=new ArrayDeque<>();
    private final Map<Long,Pending> exchanges=new LinkedHashMap<>();
    private AutomaticReplicationState state=STOPPED;
    private Record fence, campaign, durablePromise;
    private AutomaticRecovery.Basis ownBasis;
    private AutomaticRecovery.Selection selection;
    private String quorumPeer;
    // Scheduling hints only: never retained authority or an exclusion from voting.
    private String failedQuorumPeer,deferredPreparePeer;
    private Operation operation;
    private Message preparing;
    private Reconstruct reconstruction;
    private Publish publication;
    private Runnable imageContinuation;
    private byte[] image;
    private int imageIndex=-1,publishedIndex,lastProven;
    private long now,maxEpoch,serial,electionAt=Long.MAX_VALUE,heartbeatAt=Long.MAX_VALUE,
            campaignDeadline=Long.MAX_VALUE,heartbeatSequence,progress,lastHeartbeat,lastStage,lastProgress;

    AutomaticProtocol(AutomaticStore store,LongSupplier randomness,Supplier<UUID> incarnations) {
        this(store,randomness,incarnations,null);
    }
    AutomaticProtocol(AutomaticStore store,LongSupplier randomness,Supplier<UUID> incarnations,
            java.util.function.BiConsumer<String,Map<String,Object>> observer) {
        this.observer=observer;
        this.store=Objects.requireNonNull(store);this.randomness=Objects.requireNonNull(randomness);
        this.incarnations=Objects.requireNonNull(incarnations);manifest=store.manifest();bounds=store.bounds();
        policy=store.leadershipPolicy();local=text(store.status(),"node");
        peers=nodes(manifest.value()).stream().filter(n->!n.equals(local)).toList();
        fence=durablePromise=store.promised();maxEpoch=epoch(fence);lastProven=proven();
    }
    static long nextEpoch(long observed,int rank) {
        capacity(observed>=1&&rank>=0&&rank<3,"campaign epoch/rank");
        try {return Math.addExact(Math.multiplyExact(observed==1?0:Math.addExact((observed-2)/3,1),3),rank+2);}
        catch(ArithmeticException error) {throw failure(CAPACITY_EXCEEDED,"campaign epoch exhausted",error);}
    }
    private static long epoch(Record ballot) {return number(ballot.value(),"epoch");}
    private static boolean same(Record a,Record b) {return a!=null&&b!=null&&Arrays.equals(a.bytes(),b.bytes());}
    private long nextId() {capacity(serial<Long.MAX_VALUE,"protocol identity exhausted");return ++serial;}
    private void progress() {capacity(progress<Long.MAX_VALUE,"recovery progress exhausted");progress++;}
    private long after(long millis) {
        try {return Math.addExact(now,millis);}
        catch(ArithmeticException error) {throw failure(CAPACITY_EXCEEDED,"protocol clock exhausted",error);}
    }
    private void clock(long value) {need(value>=now,"monotonic elapsed clock");now=value;}
    private void room() {capacity(actions.size()<=MAX_ACTIONS-8,"protocol action backpressure");}
    private void emit(Action action) {capacity(actions.size()<MAX_ACTIONS,"protocol action bound");actions.add(action);}
    private int proven() {return lastProven=((Number)store.status().get("provenThrough")).intValue();}
    private void armElection() {
        long width=(long)policy.maxElectionTimeoutMillis()-policy.minElectionTimeoutMillis()+1;
        electionAt=after(policy.minElectionTimeoutMillis()+Math.floorMod(randomness.getAsLong(),width));
        if(observer!=null)observer.accept("ELECTION_TIMER_ARMED",Map.of("epoch",epoch(fence)));
    }
    synchronized List<Action> drain() {var result=List.copyOf(actions);actions.clear();return result;}
    synchronized Record promise() {return durablePromise;}
    synchronized void restored(byte[] application) {
        need(state==STOPPED,"initial restoration precedes start");
        var snapshot=store.provenSnapshot(application);image=application.clone();
        imageIndex=publishedIndex=AutomaticRecovery.index(snapshot);
    }
    synchronized boolean maintenanceCurrent(Record ballot) {
        return state!=STOPPED&&state!=STARTING&&state!=FAILED&&state!=AutomaticReplicationState.CLOSED
                &&same(fence,ballot)&&same(durablePromise,ballot);
    }
    synchronized Record maintenanceSnapshot() {
        if(state!=LEADER_READY||operation!=null||publication!=null||reconstruction!=null||imageIndex!=proven()||publishedIndex!=proven())return null;
        return store.provenSnapshot(image);
    }
    synchronized void observePromise(Record observed) {
        context(observed,manifest);
        if(epoch(observed)>epoch(fence)) {maxEpoch=Math.max(maxEpoch,epoch(observed));abandon(STALE_EPOCH);fence=observed;}
    }
    synchronized void rejoin(Record ballot,Record snapshot) {
        need(maintenanceCurrent(ballot)&&campaign==null&&preparing==null&&reconstruction==null&&publication==null,"rejoin requires quiescent current follower");
        store.installProven(snapshot);imageIndex=-1;proven();
        // Installation is durable recovery, never a vote or public follower publication.
        armElection();
    }
    synchronized AutomaticRecovery.Basis frozen(Record ballot) {
        need(state!=STOPPED&&state!=STARTING&&state!=FAILED&&state!=AutomaticReplicationState.CLOSED
                &&same(fence,ballot)&&same(durablePromise,ballot),"frozen basis no longer current");
        return store.prepare(ballot.bytes(),text(ballot.value(),"proposer"),new byte[0]);
    }
    synchronized View view() {
        return new View(state,epoch(durablePromise),maxEpoch,state==FAILED||state==AutomaticReplicationState.CLOSED?lastProven:proven(),publishedIndex,exchanges.size(),
                reconstruction!=null||publication!=null);
    }
    synchronized void start(long time) {
        clock(time);room();need(state==STOPPED,"protocol already started");state=STARTING;
        withImage(()->{store.resumeInitialCheckpoint(image);state=FOLLOWER;armElection();});
    }
    private void withImage(Runnable continuation) {
        imageContinuation=continuation;
        if(imageIndex==proven()) {imageContinuation=null;continuation.run();return;}
        if(reconstruction==null) {
            reconstruction=new Reconstruct(nextId(),store.replay());emit(reconstruction);
        }
    }
    synchronized void reconstructed(long id,byte[] application,Throwable error,long time) {
        clock(time);room();need(reconstruction!=null&&reconstruction.id()==id,"unknown application reconstruction");
        var completed=reconstruction;reconstruction=null;
        if(state==AutomaticReplicationState.CLOSED||state==FAILED)return;
        if(error!=null) {fail(STORAGE_FAILURE);return;}
        capacity(application!=null&&application.length<=IMAGE,"application image bound");
        image=application.clone();imageIndex=completed.replay().through();
        Runnable next=imageContinuation;imageContinuation=null;
        if(next!=null) try {withImage(next);} catch(AutomaticReplicationException failure) {fail(failure.reason());}
    }
    synchronized void tick(long time) {
        clock(time);room();if(state==STOPPED||state==STARTING||state==FAILED||state==AutomaticReplicationState.CLOSED)return;
        if(operation!=null&&now>=operation.deadline||campaign!=null&&state!=LEADER_READY&&now>=campaignDeadline)
            abandon(DEADLINE_EXCEEDED);
        for(Pending pending:List.copyOf(exchanges.values())) {
            if(!exchanges.containsKey(pending.message.id()))continue;
            if(now>=pending.deadline) {exchangeFailed(pending.message.id());continue;}
            if(now>=pending.retryAt) {pending.retryAt=Long.MAX_VALUE;pending.attempts++;emit(new Send(pending.message));}
        }
        if(campaign!=null&&now>=heartbeatAt) {
            capacity(heartbeatSequence<Long.MAX_VALUE,"heartbeat sequence exhausted");heartbeatSequence++;
            for(String peer:peers) if(exchanges.values().stream().noneMatch(p->p.message.recipient().equals(peer)&&p.message.kind()==Kind.HEARTBEAT))
                send(peer,Kind.HEARTBEAT,new Pulse(heartbeatSequence,state==LEADER_READY,progress,0));
            heartbeatAt=after(policy.heartbeatIntervalMillis());
        }
        if(campaign==null&&preparing==null&&publication==null&&now>=electionAt) beginCampaign();
    }
    private void beginCampaign() {
        try {
            long value=nextEpoch(Math.max(maxEpoch,epoch(store.promised())),nodes(manifest.value()).indexOf(local));
            String incarnation=Objects.requireNonNull(incarnations.get()).toString();
            need(!ZERO.equals(incarnation)&&!incarnation.equals(store.promised().value().get("incarnation")),"fresh campaign incarnation");
            campaign=decode(encode("PROMISE",Map.of("manifestDigest",manifest.digest(),"epoch",value,"proposer",local,"incarnation",incarnation)),"PROMISE");
            fence=campaign;maxEpoch=value;state=CANDIDATE;progress=1;campaignDeadline=after(policy.operationTimeoutMillis());
            electionAt=Long.MAX_VALUE;heartbeatAt=after(policy.heartbeatIntervalMillis());
            if(observer!=null)observer.accept("CAMPAIGN_BEGIN",Map.of("ballot",b64(campaign.bytes())));
            Record expected=campaign;
            withImage(()->{
                if(!same(campaign,expected))return;
                // Own promise and immutable basis are forced before any outbound PREPARE.
                ownBasis=store.prepare(expected.bytes(),local,image);
                durablePromise=store.promised();
                // After a failed activation, give the other voter one bounded
                // PREPARE opportunity. Otherwise a fast unusable voter can win
                // every campaign before a slower healthy basis finishes.
                deferredPreparePeer=failedQuorumPeer;
                for(String peer:peers)if(!peer.equals(deferredPreparePeer))send(peer,Kind.PREPARE,null);
            });
        } catch(AutomaticReplicationException error) {fail(error.reason());}
    }
    private void send(String peer,Kind kind,Object value) {
        capacity(exchanges.values().stream().filter(p->p.message.recipient().equals(peer)).count()<2,"two control exchanges per peer");
        var message=new Message(nextId(),kind,local,peer,campaign,false,true,value,null);
        exchanges.put(message.id(),new Pending(message,after(bounds.requestTimeoutMillis())));emit(new Send(message));
    }
    synchronized void transportFailed(long id,long time) {
        clock(time);room();Pending pending=exchanges.get(id);if(pending==null)return;
        if(now>=pending.deadline||pending.attempts>bounds.maxRetryAttempts()) {exchangeFailed(id);return;}
        // Retransmit the exact same immutable request and ID, within the original deadline.
        pending.retryAt=Math.min(pending.deadline,after(bounds.retryBackoffMillis()));
    }
    private void exchangeFailed(long id) {
        Pending pending=exchanges.remove(id);if(pending==null)return;
        Kind kind=pending.message.kind();
        if(kind==Kind.HEARTBEAT)return;
        if(kind==Kind.PREPARE) {
            if(exchanges.values().stream().anyMatch(p->p.message.kind()==Kind.PREPARE))return;
            if(deferredPreparePeer!=null&&state==CANDIDATE&&campaign!=null&&now<campaignDeadline) {
                String peer=deferredPreparePeer;deferredPreparePeer=null;
                send(peer,Kind.PREPARE,null);return;
            }
        }
        abandon(QUORUM_UNAVAILABLE);
    }
    synchronized void receive(Message message,long time) {
        clock(time);room();
        need(peers.contains(message.sender())&&local.equals(message.recipient())&&message.id()>0,"protocol endpoint/correlation");
        Record ballot=decode(message.ballot().bytes(),"PROMISE");context(ballot,manifest);
        need(epoch(ballot)>1,"live protocol ballot required");
        if(message.response()) {response(message,ballot);return;}
        need(message.sender().equals(ballot.value().get("proposer")),"request sender is not proposer");
        if(state==AutomaticReplicationState.CLOSED||state==FAILED||state==STARTING||state==STOPPED) {reply(message,false,NOT_READY);return;}
        try {
            if(message.kind()==Kind.PREPARE) {prepare(message,ballot);return;}
            if(!same(ballot,fence)||!same(ballot,store.promised())) {reply(message,false,STALE_EPOCH);return;}
            switch(message.kind()) {
                case INSTALL -> {
                    @SuppressWarnings("unchecked") var bases=(List<AutomaticRecovery.Basis>)message.payload();
                    need(bases.size()==2&&bases.stream().anyMatch(b->local.equals(b.record().value().get("node"))),"install quorum excludes local voter");
                    AutomaticRecovery.select(manifest,AutomaticRecovery.ballotOf(ballot),bases);
                    var frozen=store.prepare(ballot.bytes(),message.sender(),new byte[0]);
                    need(bases.stream().filter(b->local.equals(b.record().value().get("node"))).anyMatch(b->Arrays.equals(b.record().bytes(),frozen.record().bytes())),"installation substituted local frozen basis");
                    var chosen=store.select(bases);
                    if(!adopt(chosen)) {reply(message,false,CAPACITY_EXCEEDED);return;}
                    reply(message,true,chosen.record().digest());
                }
                case ACCEPT -> {var row=decode(((Record)message.payload()).bytes(),"ACCEPT");need(AutomaticRecovery.ballotOf(row).equals(AutomaticRecovery.ballotOf(ballot)),"accept envelope ballot");reply(message,true,store.accept(row.bytes()));}
                case PROOF -> {var row=decode(((Record)message.payload()).bytes(),"PROOF");need(AutomaticRecovery.ballotOf(row).equals(AutomaticRecovery.ballotOf(ballot)),"proof envelope ballot");String receipt=store.prove(row.bytes());proven();reply(message,true,receipt);}
                case HEARTBEAT -> heartbeat(message,(Pulse)message.payload());
                default -> throw failure(PROTOCOL_MISMATCH,"unsupported request",null);
            }
        } catch(AutomaticReplicationException error) {
            if(error.reason()==STORAGE_FAILURE||store.quarantined())fail(error.reason());
            reply(message,false,error.reason());
        }
    }
    private void prepare(Message message,Record ballot) {
        if(epoch(ballot)<epoch(fence)) {reply(message,false,STALE_EPOCH);return;}
        need(epoch(ballot)!=epoch(fence)||same(ballot,fence),"changed same-epoch request");
        if(epoch(ballot)>epoch(fence)) {
            abandon(STALE_EPOCH);fence=ballot;maxEpoch=Math.max(maxEpoch,epoch(ballot));
            lastHeartbeat=lastStage=lastProgress=0;
            if(preparing!=null) {reply(preparing,false,STALE_EPOCH);preparing=null;}
        }
        if(preparing!=null) {reply(message,false,CAPACITY_EXCEEDED);return;}
        state=FOLLOWER;preparing=message;
        withImage(()->{
            if(preparing!=message||!same(fence,ballot))return;
            try {
                var basis=store.prepare(ballot.bytes(),message.sender(),image);
                durablePromise=store.promised();
                preparing=null;armElection();reply(message,true,basis);
            } catch(AutomaticReplicationException error) {preparing=null;fail(error.reason());reply(message,false,error.reason());}
        });
    }
    private void heartbeat(Message message,Pulse pulse) {
        need(pulse.sequence()>0&&pulse.stage()>=0&&pulse.bytes()>=0,"heartbeat counters");
        if(pulse.sequence()>lastHeartbeat) {
            lastHeartbeat=pulse.sequence();
            if(pulse.activated()||pulse.stage()>lastStage||pulse.stage()==lastStage&&pulse.bytes()>lastProgress) {
                lastStage=pulse.stage();lastProgress=pulse.bytes();armElection();
            }
        }
        reply(message,true,pulse.sequence());
    }
    private void reply(Message request,boolean accepted,Object payload) {
        emit(new Send(new Message(request.id(),request.kind(),local,request.sender(),request.ballot(),true,accepted,payload,durablePromise)));
    }
    private void response(Message response,Record ballot) {
        Pending pending=exchanges.get(response.id());if(pending==null)return;
        Message request=pending.message;
        need(request.recipient().equals(response.sender())&&request.kind()==response.kind()&&same(request.ballot(),ballot),"uncorrelated protocol response");
        Record promised=decode(response.promised().bytes(),"PROMISE");context(promised,manifest);
        if(now>=pending.deadline) {exchangeFailed(response.id());return;}
        if(operation!=null&&now>=operation.deadline||campaign!=null&&state!=LEADER_READY&&now>=campaignDeadline) {abandon(DEADLINE_EXCEEDED);return;}
        if(epoch(promised)>epoch(fence)) {maxEpoch=Math.max(maxEpoch,epoch(promised));abandon(STALE_EPOCH);fence=promised;return;}
        if(!response.accepted()) {exchangeFailed(response.id());return;}
        need(same(promised,ballot),"acknowledgement promise differs");
        exchanges.remove(response.id());
        if(!same(campaign,ballot)||!same(store.promised(),campaign))return;
        try {
            switch(response.kind()) {
                case PREPARE -> {
                    if(state!=CANDIDATE)return;
                    var basis=(AutomaticRecovery.Basis)response.payload();
                    need(response.sender().equals(basis.record().value().get("node")),"basis responder binding");
                    capacity((long)ownBasis.image().encoded().bytes().length+basis.image().encoded().bytes().length<=bounds.maxSnapshotStagingBytes(),"prepare quorum image bound");
                    selection=store.select(List.of(ownBasis,basis));quorumPeer=response.sender();deferredPreparePeer=null;
                    if(observer!=null)observer.accept("PROMISE_QUORUM",Map.of("selected",b64(selection.record().bytes())));
                    exchanges.entrySet().removeIf(e->e.getValue().message.kind()==Kind.PREPARE);
                    if(!adopt(selection)) {abandon(CAPACITY_EXCEEDED);return;}
                    state=RECOVERING;progress();
                    send(quorumPeer,Kind.INSTALL,selection.bases());
                }
                case INSTALL -> {
                    need(state==RECOVERING&&selection.record().digest().equals(response.payload()),"selected installation binding");progress();
                    Record carried=selection.sourceAcceptance()==null?null:decode(unbase(selection.sourceAcceptance().value().get("entry")),"ENTRY");
                    commit(carried==null?fresh(9,new byte[0]):carried,0,true);
                }
                case ACCEPT -> accepted(response);
                case PROOF -> proved(response);
                case HEARTBEAT -> need(response.payload().equals(((Pulse)request.payload()).sequence()),"heartbeat response sequence");
            }
        } catch(AutomaticReplicationException error) {fail(error.reason());}
    }
    private boolean adopt(AutomaticRecovery.Selection chosen) {
        // The verified local proven prefix needs no generation rewrite. In particular,
        // duplicate INSTALL and equal-prefix elections cannot consume generation slots.
        if(AutomaticRecovery.index(chosen.snapshot())>proven()) {
            // Interrupted retirement can leave both generation slots occupied.
            // Reject before ambiguous I/O so background two-source cleanup can
            // free the slot and a later campaign can adopt the verified prefix.
            if(!store.generationAvailable(chosen.snapshot()))return false;
            store.installSelected();imageIndex=-1;proven();
        }
        return true;
    }
    private Record fresh(int operation,byte[] payload) {
        // Origin/predecessor are read from proven authority, never the last response.
        var head=store.head();int cut=head.index();
        return decode(encode("ENTRY",Map.of("manifestDigest",manifest.digest(),"originEpoch",epoch(campaign),
                "originIncarnation",campaign.value().get("incarnation"),"index",cut+1L,"operation",operation,
                "previousEpoch",head.originEpoch(),"previousIndex",(long)cut,
                "previousDigest",head.digest(),"payload",b64(payload),"payloadDigest",sha(payload))),"ENTRY");
    }
    synchronized void submit(long request,int operation,byte[] payload,long time) {
        clock(time);room();need(request>0&&operation>=1&&operation<=9,"logical request identity/operation");
        if(state!=LEADER_READY||this.operation!=null||publication!=null) {
            emit(new Completed(request,0,state==LEADER_READY?CAPACITY_EXCEEDED:NOT_READY,NOT_SUBMITTED));return;
        }
        try {commit(fresh(operation,payload.clone()),request,false);}
        catch(AutomaticReplicationException error) {
            if(this.operation==null)emit(new Completed(request,0,error.reason(),NOT_SUBMITTED));else fail(error.reason());
        }
    }
    private void commit(Record entry,long request,boolean recovery) {
        need(same(campaign,fence)&&same(campaign,store.promised())&&operation==null,"current serialized proposal");
        var value=new LinkedHashMap<String,Object>(campaign.value());value.put("entry",b64(entry.bytes()));value.put("entryDigest",entry.digest());
        Record accepted=decode(encode("ACCEPT",value),"ACCEPT");
        capacity(accepted.bytes().length<=bounds.maxFrameBytes(),"proposal frame bound");
        operation=new Operation(entry,request,after(policy.operationTimeoutMillis()),recovery);operation.issued=true;
        operation.ownReceipt=store.accept(accepted.bytes());progress();send(quorumPeer,Kind.ACCEPT,accepted);
    }
    private void accepted(Message response) {
        need(operation!=null&&operation.proof==null&&response.sender().equals(quorumPeer),"entry acknowledgement phase");
        var entry=operation.entry;long index=number(entry.value(),"index");
        need(response.payload().equals(receipt("ACCEPT_ACK",manifest.digest(),quorumPeer,campaign.value(),index,entry.digest())),"entry acknowledgement receipt");
        var value=new LinkedHashMap<String,Object>(campaign.value());value.put("index",index);value.put("entryDigest",entry.digest());value.put("previousDigest",entry.value().get("previousDigest"));
        value.put("receipts",List.of(local,quorumPeer).stream().sorted().map(n->Map.of("voter",n,"digest",n.equals(local)?operation.ownReceipt:(String)response.payload())).toList());
        operation.proof=decode(encode("PROOF",value),"PROOF");store.prove(operation.proof.bytes());proven();progress();
        send(quorumPeer,Kind.PROOF,operation.proof);
    }
    private void proved(Message response) {
        need(operation!=null&&operation.proof!=null&&response.sender().equals(quorumPeer),"proof acknowledgement phase");
        var committing=operation;long index=number(committing.entry.value(),"index");
        need(response.payload().equals(receipt("PROOF_ACK",manifest.digest(),quorumPeer,campaign.value(),index,sha(committing.proof.bytes()))),"proof acknowledgement receipt");
        Record expected=campaign;
        withImage(()->{
            if(operation!=committing||!same(campaign,expected)||!same(fence,expected))return;
            publication=new Publish(nextId(),expected,store.provenSnapshot(image));emit(publication);progress();
        });
    }
    synchronized void published(long id,Throwable error,long time) {
        clock(time);room();need(publication!=null&&publication.id()==id,"unknown publication");
        var completed=publication;publication=null;
        if(state==AutomaticReplicationState.CLOSED||state==FAILED)return;
        if(error!=null) {fail(STORAGE_FAILURE);return;}
        if(operation==null||!same(campaign,completed.ballot())||!same(fence,campaign)||!same(store.promised(),campaign))return;
        if(now>=operation.deadline||operation.campaign&&now>=campaignDeadline) {abandon(DEADLINE_EXCEEDED);return;}
        var committed=operation;operation=null;publishedIndex=AutomaticRecovery.index(completed.snapshot());
        if(committed.campaign) {
            if(number(committed.entry.value(),"operation")!=9||number(committed.entry.value(),"originEpoch")!=epoch(campaign)
                    ||!committed.entry.value().get("originIncarnation").equals(campaign.value().get("incarnation"))) {
                commit(fresh(9,new byte[0]),0,true);return;
            }
            state=LEADER_READY;failedQuorumPeer=null;campaignDeadline=Long.MAX_VALUE;heartbeatAt=now;progress();
        } else emit(new Completed(committed.request,publishedIndex,null,NOT_APPLICABLE));
    }
    synchronized void cancel(long request,long time) {
        clock(time);room();if(operation!=null&&!operation.campaign&&operation.request==request)abandon(NOT_READY);
    }
    private void abandon(AutomaticReplicationException.Reason reason) {
        if(state==RECOVERING&&quorumPeer!=null&&(reason==QUORUM_UNAVAILABLE||reason==DEADLINE_EXCEEDED))
            failedQuorumPeer=quorumPeer;
        deferredPreparePeer=null;
        if(operation!=null&&!operation.campaign)emit(new Completed(operation.request,0,reason,operation.issued?INDETERMINATE:NOT_SUBMITTED));
        operation=null;campaign=null;ownBasis=null;selection=null;quorumPeer=null;imageContinuation=null;
        exchanges.clear();actions.removeIf(a->a instanceof Send s&&!s.message.response());
        campaignDeadline=heartbeatAt=Long.MAX_VALUE;state=UNAVAILABLE;armElection();
    }
    private void fail(AutomaticReplicationException.Reason reason) {
        abandon(reason);state=FAILED;electionAt=Long.MAX_VALUE;
    }
    synchronized void quiesce() {
        room();if(state!=AutomaticReplicationState.CLOSED) {
            if(preparing!=null) {reply(preparing,false,AutomaticReplicationException.Reason.CLOSED);preparing=null;}
            abandon(AutomaticReplicationException.Reason.CLOSED);state=AutomaticReplicationState.CLOSED;electionAt=Long.MAX_VALUE;
        }
    }
    @Override public synchronized void close() {
        quiesce();
        if(reconstruction!=null||publication!=null)throw failure(DEADLINE_EXCEEDED,"application work must quiesce before authority unlock",null);
        store.close();
    }
}
