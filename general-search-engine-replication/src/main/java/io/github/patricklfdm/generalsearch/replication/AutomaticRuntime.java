package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.AutomaticRecords.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Reason.*;
import static io.github.patricklfdm.generalsearch.replication.AutomaticReplicationException.Outcome.*;
import io.github.patricklfdm.generalsearch.replication.AutomaticRecords.Record;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineConfiguration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.*;
import java.time.Instant;
import java.time.Duration;
import io.github.patricklfdm.generalsearch.durability.*;

/** Internal runtime over retained sealed authority. Public lifecycle/read admission belongs to Phase 4. */
final class AutomaticRuntime<K,T> implements AutoCloseable {
    interface Events {
        Events NONE=(name,value)->{};
        void at(String name,Map<String,Object> value) throws java.io.IOException;
    }
    private final Events events;
    private final AutomaticStore store;
    private final AutomaticProtocol protocol;
    private final AutomaticApplication<K,T> application;
    private final AutomaticTransport transport;
    private final AutomaticRejoin rejoin;
    private final Record manifest;
    private final String local;
    private final ReplicationBounds bounds;
    private final AutomaticLeadershipPolicy policy;
    private final Object callbackOwner;
    private final List<ReplicationMember> members;
    private final CompletableFuture<AutomaticReplicationStatus> started=new CompletableFuture<>();
    private final Map<String,ReplicationPeerStatus> observations=new LinkedHashMap<>();
    private volatile AutomaticReplicationStatus publicStatus;
    private volatile DurabilityMetrics durability;
    private long publishedSequence;
    private long startupReplayedRecords;
    private Duration startupRecoveryDuration=Duration.ZERO, startupRebuildDuration=Duration.ZERO;
    private Instant quorumSuccess;
    private boolean startupCompletionQueued;
    private String observedLeader;
    private long observedLeaderEpoch;
    private final UUID trace=UUID.randomUUID();
    private final AtomicLong ids=new AtomicLong();
    private final long origin=System.nanoTime();
    private final ArrayBlockingQueue<Runnable> inputs=new ArrayBlockingQueue<>(32),completions=new ArrayBlockingQueue<>(16);
    private final ThreadPoolExecutor network=pool("network",4,4),app=pool("application",1,4),clients=pool("completion",1,2);
    private final Semaphore submission=new Semaphore(1);
    private final Map<Long,CompletableFuture<AutomaticProtocol.Message>> incoming=new HashMap<>();
    private final Map<Long,CompletableFuture<Long>> requests=new HashMap<>();
    private final Thread control;
    private volatile AutomaticProtocol.View view;
    private volatile Record promise;
    private volatile Throwable failure;
    private volatile Throwable lastExchangeFailure;
    private volatile boolean closing,terminated;

    private static ThreadPoolExecutor pool(String name,int threads,int queued) {
        return new ThreadPoolExecutor(threads,threads,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(queued),
                task->Thread.ofPlatform().daemon().name("gse-automatic-"+name).unstarted(task));
    }
    AutomaticRuntime(AutomaticReplicationGroupConfig<K,T> config,SearchEngineConfiguration<K,T> captured,
                     byte[] manifestBytes,AutomaticStore.Faults faults,AutomaticTransport.Events events) {
        this(config,captured,manifestBytes,faults,events,Events.NONE);
    }
    AutomaticRuntime(AutomaticReplicationGroupConfig<K,T> config,SearchEngineConfiguration<K,T> captured,
                     byte[] manifestBytes,AutomaticStore.Faults faults,AutomaticTransport.Events transportEvents,Events events) {
        this(config,captured,manifestBytes,faults,transportEvents,events,null);
    }
    AutomaticRuntime(AutomaticReplicationGroupConfig<K,T> config,SearchEngineConfiguration<K,T> captured,
                     byte[] manifestBytes,AutomaticStore.Faults faults,AutomaticTransport.Events transportEvents,Events events,Object callbackOwner) {
        long startupBegin=System.nanoTime();
        this.events=events;
        this.callbackOwner=callbackOwner;members=config.members();
        for(var m:members) if(!m.nodeId().equals(config.localNodeId())) observations.put(m.nodeId().value(),new ReplicationPeerStatus(m.nodeId(),false,0,0,0,Optional.empty()));
        bounds=config.bounds();policy=config.leadershipPolicy();local=config.localNodeId().value();manifest=decode(manifestBytes,"MANIFEST");
        need(config.groupId().value().toString().equals(manifest.value().get("groupId"))&&config.configurationId().equals(manifest.value().get("configurationId")),"runtime group configuration");
        need(config.members().stream().map(m->Map.of("node",m.nodeId().value(),"host",m.endpoint().host(),"port",(long)m.endpoint().port())).toList().equals(manifest.value().get("members")),"runtime members/order");
        store=AutomaticStore.open(config.replicaDirectory(),manifestBytes,local,bounds,faults);
        AutomaticApplication<K,T> opening=null;AutomaticTransport listening=null;
        try {
            need(store.leadershipPolicy().equals(policy),"runtime policy differs from seal");
            if(callbackOwner!=null) AutomaticPublicAdmission.verify(config,captured);
            long rebuildBegin=System.nanoTime();
            opening=new AutomaticApplication<>(captured,config.materialization(),bounds);opening.validate(manifest,config.materialization());application=opening;
            protocol=new AutomaticProtocol(store,()->ThreadLocalRandom.current().nextLong(),UUID::randomUUID);
            if(callbackOwner!=null) {
                var replay=store.replay();startupReplayedRecords=replay.entries().size();
                byte[] restored=application.reconstruct(replay);application.publish(store.provenSnapshot(restored));protocol.restored(restored);
                publishedSequence=application.sequence();
            }
            startupRebuildDuration=Duration.ofNanos(System.nanoTime()-rebuildBegin);
            startupRecoveryDuration=Duration.ofNanos(System.nanoTime()-startupBegin);
            promise=protocol.promise();view=protocol.view();
            refresh();
            listening=new AutomaticTransport(manifest,local,bounds,this::handle,transportEvents);transport=listening;
            rejoin=new AutomaticRejoin(store,protocol,this::controlled,this::send,this::now,this::id,events);
            control=Thread.ofPlatform().daemon().name("gse-automatic-control-"+local).unstarted(this::loop);
            inputs.add(()->protocol.start(now()));control.start();
        } catch(RuntimeException|Error error) {
            if(listening!=null)listening.close();if(opening!=null)opening.close();store.close();
            network.shutdownNow();app.shutdownNow();clients.shutdownNow();throw error;
        }
    }
    private long now() {return TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-origin);}
    private long id() {long id=ids.incrementAndGet();capacity(id>0,"runtime correlation exhausted");return id;}
    AutomaticProtocol.View view() {return view;}
    Throwable failure() {return failure;}
    Throwable lastExchangeFailure() {return lastExchangeFailure;}
    Throwable lastRecoveryFailure() {return rejoin.lastFailure();}
    Throwable lastRecoveryRejection() {return rejoin.lastRejected();}
    CompletableFuture<AutomaticReplicationStatus> started() {return started.copy();}
    AutomaticReplicationStatus status() {return publicStatus;}
    DurabilityMetrics durability() {return durability;}
    private void applicationTask(Runnable task) {app.execute(()->AutomaticContext.run(callbackOwner,task));}
    // Test/internal inspection only; this is deliberately not a public strong-read implementation.
    <R> CompletableFuture<R> inspectLocal(Function<SearchEngine<K,T>,R> action) {
        var result=new CompletableFuture<R>();
        try {applicationTask(()->{try {result.complete(application.readLocal(action));}catch(Throwable e){result.completeExceptionally(e);}});}
        catch(RejectedExecutionException error) {result.completeExceptionally(error);}return result;
    }
    CompletableFuture<Long> submit(int operation,Function<ReplicaApplication<K,T>,byte[]> encoder) {
        var result=new CompletableFuture<Long>();
        if(closing||failure!=null||!submission.tryAcquire()) {result.completeExceptionally(outcome(closing?CLOSED:CAPACITY_EXCEEDED,NOT_SUBMITTED));return result;}
        long request=id(),deadline=now()+policy.operationTimeoutMillis();
        try {enqueue(()->{
            if(view.state()!=AutomaticReplicationState.LEADER_READY) {finish(result,null,outcome(NOT_READY,NOT_SUBMITTED));return;}
            Record expected=promise;int cut=view.publishedIndex();
            try {applicationTask(()->{
                byte[] payload=null;Throwable error=null;
                try {need(operation>=1&&operation<=9,"application operation");payload=Objects.requireNonNull(encoder.apply(application.encoder())).clone();application.stage(operation,payload);}
                catch(Throwable e){error=e;}
                byte[] bytes=payload;Throwable rejected=error;
                complete(()->{
                    if(rejected!=null) {
                        Throwable cause=rejected;
                        while(cause instanceof CompletionException&&cause.getCause()!=null)cause=cause.getCause();
                        if(cause instanceof ReplicationException old) {
                            AutomaticReplicationException.Reason reason;
                            try{reason=AutomaticReplicationException.Reason.valueOf(old.reason().name());}catch(IllegalArgumentException ignored){reason=STORAGE_FAILURE;}
                            cause=new AutomaticReplicationException(reason,NOT_SUBMITTED,Optional.empty(),old.getMessage(),old);
                        }
                        finish(result,null,cause);return;
                    }
                    if(closing||now()>=deadline||!Arrays.equals(expected.bytes(),promise.bytes())||view.state()!=AutomaticReplicationState.LEADER_READY||view.publishedIndex()!=cut) {
                        finish(result,null,outcome(closing?CLOSED:now()>=deadline?DEADLINE_EXCEEDED:NOT_READY,NOT_SUBMITTED));return;
                    }
                    if(result.isCancelled()) {finish(result,null,outcome(NOT_READY,NOT_SUBMITTED));return;}
                    requests.put(request,result);protocol.submit(request,operation,bytes,now());
                });
            });}catch(RejectedExecutionException error){finish(result,null,outcome(CAPACITY_EXCEEDED,NOT_SUBMITTED));}
        });}catch(RuntimeException error){submission.release();result.completeExceptionally(error);}
        result.whenComplete((v,e)->{if(result.isCancelled())try{enqueue(()->protocol.cancel(request,now()));}catch(RuntimeException ignored){}});
        return result;
    }
    private static AutomaticReplicationException outcome(AutomaticReplicationException.Reason reason,AutomaticReplicationException.Outcome outcome) {
        return new AutomaticReplicationException(reason,outcome,Optional.empty(),"automatic runtime "+reason);
    }
    private void finish(CompletableFuture<Long> future,Long value,Throwable error) {
        clients.execute(()->{submission.release();if(error==null)future.complete(value);else future.completeExceptionally(error);});
    }
    private void enqueue(Runnable task) {
        if(closing||terminated||!inputs.offer(task))throw outcome(closing?CLOSED:CAPACITY_EXCEEDED,NOT_SUBMITTED);
    }
    private void complete(Runnable task) {
        // Reserved mailbox: at most four outgoing pipelines, eight inbound exchanges and two application completions.
        if(!completions.offer(task)) {failure=outcome(CAPACITY_EXCEEDED,INDETERMINATE);closing=true;}
    }
    private <R> R controlled(Callable<R> task) throws Exception {
        var answer=new CompletableFuture<R>();enqueue(()->{try{answer.complete(task.call());}catch(Throwable error){answer.completeExceptionally(error);}});
        return answer.get(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS);
    }
    private void loop() {
        while(!terminated)try {
            for(int i=0;i<16;i++){Runnable task=completions.poll();if(task==null)break;task.run();flush();}
            Runnable task=inputs.poll(20,TimeUnit.MILLISECONDS);if(task!=null)task.run();
            if(!closing) {protocol.tick(now());rejoin.tick();}flush();
        }catch(InterruptedException error){if(!terminated){failure=error;closing=true;}}
        catch(Throwable error){failure=error;closing=true;try{protocol.quiesce();flush();}catch(Throwable ignored){}}
    }
    private void flush() {
        promise=protocol.promise();view=protocol.view();
        var clientCompletions=new ArrayList<Runnable>();
        for(var action:protocol.drain()) {
            if(action instanceof AutomaticProtocol.Send send) {
                var message=send.message();
                if(message.response()) {var future=incoming.remove(message.id());if(future!=null)future.complete(message);}
                else try {network.execute(()->{
                    try {var reply=exchange(message);complete(()->{protocol.receive(reply,now());observe(message,reply);});}
                    catch(Throwable error){lastExchangeFailure=error;complete(()->{protocol.transportFailed(message.id(),now());unreachable(message.recipient());});}
                });}catch(RejectedExecutionException error){protocol.transportFailed(message.id(),now());}
            }else if(action instanceof AutomaticProtocol.Reconstruct rebuild) {
                applicationTask(()->{byte[] image=null;Throwable failure=null;try{image=application.reconstruct(rebuild.replay());}catch(Throwable e){failure=e;}
                    byte[] value=image;Throwable error=failure;complete(()->protocol.reconstructed(rebuild.id(),value,error,now()));});
            }else if(action instanceof AutomaticProtocol.Publish publish) {
                applicationTask(()->{Throwable failure=null;try{application.publish(publish.snapshot());events.at("PUBLISHED",Map.of("ballot",b64(publish.ballot().bytes()),"snapshot",b64(publish.snapshot().bytes())));}catch(Throwable e){failure=e;}
                    Throwable error=failure;complete(()->{protocol.published(publish.id(),error,now());
                        if(error==null&&protocol.view().publishedIndex()==AutomaticRecovery.index(publish.snapshot()))publishedSequence=number(publish.snapshot().value(),"applicationSequence");});});
            }else if(action instanceof AutomaticProtocol.Completed done) {
                var future=requests.remove(done.request());if(future!=null)clientCompletions.add(()->finish(future,done.index(),done.reason()==null?null:outcome(done.reason(),done.outcome())));
            }
        }
        refresh();
        for(var completion:clientCompletions)completion.run();
    }
    private void observe(AutomaticProtocol.Message request,AutomaticProtocol.Message reply) {
        var old=observations.get(request.recipient());if(old==null)return;
        long durable=old.durableIndex(),matched=old.matchIndex();
        if(reply.accepted()&&(request.kind()==AutomaticProtocol.Kind.ACCEPT||request.kind()==AutomaticProtocol.Kind.PROOF)) {
            var record=(Record)request.payload();long index=request.kind()==AutomaticProtocol.Kind.ACCEPT?
                    number(decode(unbase(record.value().get("entry")),"ENTRY").value(),"index"):number(record.value(),"index");
            durable=Math.max(durable,index);if(request.kind()==AutomaticProtocol.Kind.PROOF)matched=Math.max(matched,index);
        }
        observations.put(request.recipient(),new ReplicationPeerStatus(old.nodeId(),true,durable,matched,old.appliedIndex(),Optional.of(Instant.now())));
        if(reply.accepted()&&protocol.view().state()==AutomaticReplicationState.LEADER_READY&&Arrays.equals(reply.ballot().bytes(),protocol.promise().bytes()))quorumSuccess=Instant.now();
    }
    private void unreachable(String peer) {
        var old=observations.get(peer);if(old!=null)observations.put(peer,new ReplicationPeerStatus(old.nodeId(),false,old.durableIndex(),old.matchIndex(),old.appliedIndex(),Optional.of(Instant.now())));
    }
    private void refresh() {
        var current=protocol.view();var promised=protocol.promise();view=current;promise=promised;var state=current.state();
        if(state==AutomaticReplicationState.STOPPED)state=AutomaticReplicationState.STARTING;
        if(observedLeaderEpoch<number(promised.value(),"epoch")||state!=AutomaticReplicationState.LEADER_READY)observedLeader=null;
        if(state==AutomaticReplicationState.LEADER_READY){observedLeader=local;observedLeaderEpoch=current.promisedEpoch();}
        publicStatus=new AutomaticReplicationStatus(new ReplicationNodeId(local),state,Optional.ofNullable(observedLeader).map(ReplicationNodeId::new),
                number(promised.value(),"epoch")<=1?Optional.empty():Optional.of(new ReplicationNodeId(text(promised.value(),"proposer"))),number(promised.value(),"epoch"),UUID.fromString(text(promised.value(),"incarnation")),
                state==AutomaticReplicationState.LEADER_READY?current.promisedEpoch():0,current.provenIndex(),current.publishedIndex(),publishedSequence,
                submission.availablePermits()==0?1:0,Optional.ofNullable(quorumSuccess),List.copyOf(observations.values()));
        if(state!=AutomaticReplicationState.CLOSED&&!store.quarantined()) {
            var counts=store.diagnosticCounts();
            durability=new DurabilityMetrics(state==AutomaticReplicationState.FAILED?DurabilityStatus.FAILED:DurabilityStatus.OPEN,
                    counts.get("sequence"),counts.get("checkpointSequence"),0,counts.get("walRecords"),counts.get("walBytes"),counts.get("retainedBytes"),
                    startupReplayedRecords==0?RecoverySource.CHECKPOINT_ONLY:RecoverySource.CHECKPOINT_AND_WAL,startupReplayedRecords,startupRecoveryDuration,startupRebuildDuration,Optional.empty());
        }
        if(!startupCompletionQueued&&!started.isDone()&&state!=AutomaticReplicationState.STARTING) {
            startupCompletionQueued=true;
            var snapshot=publicStatus;
            clients.execute(()->{if(snapshot.state()==AutomaticReplicationState.FAILED||snapshot.state()==AutomaticReplicationState.CLOSED)started.completeExceptionally(outcome(NOT_READY,NOT_APPLICABLE));else started.complete(snapshot);});
        }
    }

    record Captured<R>(CompletableFuture<Void> begun,CompletableFuture<R> result) { }
    <R> Captured<R> capture(long epoch,long index,long deadline,Function<AutomaticApplication<K,T>,R> action) {
        var begun=new CompletableFuture<Void>();var result=new CompletableFuture<R>();
        try { applicationTask(()->{
            try {
                if(closing||result.isCancelled())throw outcome(CLOSED,NOT_APPLICABLE);
                if(System.nanoTime()>=deadline)throw outcome(DEADLINE_EXCEEDED,NOT_APPLICABLE);
                // Validate at the capture point, not against a possibly older diagnostic cache.
                // The application worker keeps this view alive; no query callback runs under the protocol monitor.
                synchronized(protocol) {
                    var status=protocol.view();
                    if(status.state()!=AutomaticReplicationState.LEADER_READY||status.promisedEpoch()!=epoch||application.index()!=index)
                        throw outcome(STALE_EPOCH,NOT_APPLICABLE);
                }
                begun.complete(null);result.complete(action.apply(application));
            } catch(Throwable error){begun.completeExceptionally(error);result.completeExceptionally(error);}
        });} catch(Throwable error){begun.completeExceptionally(error);result.completeExceptionally(error);}
        return new Captured<>(begun,result);
    }
    CompletableFuture<Void> checkpoint(long deadline) {
        var result=new CompletableFuture<Void>();
        try { enqueue(()->{
            try {
                if(System.nanoTime()>=deadline)throw outcome(DEADLINE_EXCEEDED,NOT_APPLICABLE);
                var state=protocol.view();var status=store.status();
                if(state.applicationPending()||!Set.of(AutomaticReplicationState.LEADER_READY,AutomaticReplicationState.FOLLOWER,AutomaticReplicationState.UNAVAILABLE).contains(state.state())
                        ||!status.get("acceptedThrough").equals(status.get("provenThrough")))throw outcome(NOT_READY,NOT_APPLICABLE);
                var replay=store.replay();var promised=protocol.promise();
                applicationTask(()->{
                    byte[] image=null;Throwable failed=null;try{image=application.checkpointImage(replay);}catch(Throwable error){failed=error;}
                    byte[] bytes=image;Throwable error=failed;
                    complete(()->{
                        try {
                            if(error!=null)throw new CompletionException(error);
                            if(System.nanoTime()>=deadline)throw outcome(DEADLINE_EXCEEDED,NOT_APPLICABLE);
                            var fresh=store.status();
                            if(closing||protocol.view().applicationPending()||!Arrays.equals(promised.bytes(),protocol.promise().bytes())
                                    ||((Number)fresh.get("provenThrough")).intValue()!=replay.through()||!fresh.get("acceptedThrough").equals(fresh.get("provenThrough")))throw outcome(NOT_READY,NOT_APPLICABLE);
                            var snapshot=store.provenSnapshot(bytes);if(!store.generationAvailable(snapshot))throw outcome(CAPACITY_EXCEEDED,NOT_APPLICABLE);
                            store.checkpoint(bytes);refresh();result.complete(null);
                        }catch(Throwable failure){result.completeExceptionally(failure);}
                    });
                });
            }catch(Throwable error){result.completeExceptionally(error);}
        });}catch(Throwable error){result.completeExceptionally(error);}return result;
    }
    private Map<String,Object> wire(AutomaticProtocol.Message message,String type,Map<String,Object> payload) {
        return AutomaticWire.message(manifest,message.ballot(),local,message.recipient(),type,trace,message.id(),payload);
    }
    private Map<String,Object> send(Map<String,Object> request) throws Exception {
        var response=transport.exchange(text(request,"recipient"),request).get(bounds.requestTimeoutMillis()+100L,TimeUnit.MILLISECONDS);
        AutomaticWire.correlated(request,response);return response;
    }
    private AutomaticProtocol.Message exchange(AutomaticProtocol.Message message) throws Exception {
        var value=new LinkedHashMap<String,Object>();String type;
        switch(message.kind()) {
            case PREPARE -> {type="PREPARE";value.put("nonce",new UUID(0,message.id()).toString());}
            case INSTALL -> {
                type="SELECTED_OFFER";
                @SuppressWarnings("unchecked") var bases=(List<AutomaticRecovery.Basis>)message.payload();
                var selected=AutomaticRecovery.select(manifest,AutomaticRecovery.ballotOf(message.ballot()),bases);
                value.put("response",false);value.put("selected",b64(selected.record().bytes()));value.put("bases",bases.stream().map(b->b64(b.record().bytes())).toList());
            }
            case ACCEPT -> {type="ACCEPT";value.put("acceptance",b64(((Record)message.payload()).bytes()));}
            case PROOF -> {type="COMMIT_PROOF";value.put("proof",b64(((Record)message.payload()).bytes()));}
            case HEARTBEAT -> {
                type="HEARTBEAT";var p=(AutomaticProtocol.Pulse)message.payload();value.put("sequence",p.sequence());value.put("activated",p.activated());
                value.put("stage",p.stage());value.put("progressBytes",p.bytes());value.put("provenIndex",(long)view.provenIndex());
            }
            default -> throw new IllegalStateException();
        }
        var request=wire(message,type,value);var response=send(request);var payload=object(response.get("payload"));
        Record promised=message.ballot();boolean accepted=!response.get("type").equals("REJECT");Object decoded;
        if(!accepted) {
            var grant=new LinkedHashMap<>(object(payload.get("promised")));grant.put("manifestDigest",manifest.digest());promised=decode(encode("PROMISE",grant),"PROMISE");decoded=text(payload,"reason");
        }else decoded=switch(message.kind()) {
            case PREPARE -> {need(response.get("type").equals("PROMISE")&&payload.get("nonce").equals(value.get("nonce")),"prepare response nonce/type");yield fetchBasis(decode(unbase(payload.get("basis")),"BASIS"),message.ballot());}
            case INSTALL -> {need(response.get("type").equals("SELECTED_OFFER")&&Boolean.TRUE.equals(payload.get("response"))&&payload.get("selected").equals(value.get("selected"))&&payload.get("bases").equals(value.get("bases")),"selected response binding");yield digest(unbase(value.get("selected")));}
            case ACCEPT -> {need(response.get("type").equals("ACCEPT_ACK"),"accept response type");yield payload.get("receipt");}
            case PROOF -> {need(response.get("type").equals("COMMIT_PROOF_ACK"),"proof response type");yield payload.get("receipt");}
            case HEARTBEAT -> {need(response.get("type").equals("HEARTBEAT_ACK"),"heartbeat response type");yield number(payload,"sequence");}
        };
        return new AutomaticProtocol.Message(message.id(),message.kind(),message.recipient(),local,message.ballot(),true,accepted,decoded,promised);
    }
    private AutomaticRecovery.Basis fetchBasis(Record basis,Record ballot) throws Exception {
        context(basis,manifest);String owner=text(basis.value(),"node");
        if(owner.equals(local)) {
            var own=controlled(()->protocol.frozen(ballot));need(Arrays.equals(own.record().bytes(),basis.bytes()),"local frozen descriptor changed");return own;
        }
        int length=Math.toIntExact(number(basis.value(),"imageBytes"));capacity(length<=Math.min(IMAGE,bounds.maxSnapshotStagingBytes()),"basis download capacity");
        byte[] bytes=new byte[length];long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
        for(int offset=0;offset<length;) {
            need(System.nanoTime()<deadline,"basis download deadline");
            int count=Math.min(length-offset,Math.min(bounds.snapshotChunkBytes(),Math.max(4096,(bounds.maxFrameBytes()-4096)/4*3)));
            var payload=Map.<String,Object>of("basisId",basis.value().get("basisId"),"action","REQUEST","offset",(long)offset,"maxChunkBytes",(long)Math.max(4096,count),"chunkBytes",0L,"chunk","","chunkDigest",sha(new byte[0]));
            var request=AutomaticWire.message(manifest,ballot,local,owner,"BASIS_CHUNK",trace,id(),payload);
            var response=send(request);need(response.get("type").equals("BASIS_CHUNK"),"basis unavailable");var data=object(response.get("payload"));
            byte[] chunk=unbase(data.get("chunk"));need(data.get("action").equals("DATA")&&data.get("basisId").equals(basis.value().get("basisId"))&&number(data,"offset")==offset
                    &&number(data,"maxChunkBytes")==Math.max(4096,count)&&chunk.length==count,"basis range correspondence");
            System.arraycopy(chunk,0,bytes,offset,count);offset+=count;
        }
        return AutomaticRecovery.Basis.read(basis.bytes(),bytes,manifest);
    }
    private Map<String,Object> handle(Map<String,Object> request) {
        try {
            need(!closing,"runtime closing");String type=text(request,"type");var payload=object(request.get("payload"));Record ballot=AutomaticWire.ballot(request,manifest);
            if(type.equals("HANDSHAKE"))return AutomaticWire.reply(request,type,Map.of("mode","AUTOMATIC"));
            if(rejoin.handles(type))return rejoin.handle(request);
            if(type.equals("BASIS_CHUNK")) {
                need(payload.get("action").equals("REQUEST"),"basis request direction");var basis=controlled(()->protocol.frozen(ballot));
                need(basis.record().value().get("basisId").equals(payload.get("basisId")),"expired basis identity");
                byte[] bytes=basis.image().encoded().bytes();long offset=number(payload,"offset");need(offset<bytes.length,"basis offset");
                int size=(int)Math.min(bytes.length-offset,Math.min(number(payload,"maxChunkBytes"),bounds.snapshotChunkBytes()));
                capacity(size<=(bounds.maxFrameBytes()-4096)/4*3,"basis encoded chunk capacity");
                var result=new LinkedHashMap<>(payload);result.put("action","DATA");byte[] chunk=Arrays.copyOfRange(bytes,(int)offset,(int)offset+size);
                result.put("chunk",b64(chunk));result.put("chunkBytes",(long)size);result.put("chunkDigest",sha(chunk));return AutomaticWire.reply(request,type,result);
            }
            AutomaticProtocol.Kind kind;Object decoded;
            switch(type) {
                case "PREPARE" -> {kind=AutomaticProtocol.Kind.PREPARE;decoded=null;}
                case "ACCEPT" -> {kind=AutomaticProtocol.Kind.ACCEPT;decoded=decode(unbase(payload.get("acceptance")),"ACCEPT");}
                case "COMMIT_PROOF" -> {kind=AutomaticProtocol.Kind.PROOF;decoded=decode(unbase(payload.get("proof")),"PROOF");}
                case "HEARTBEAT" -> {kind=AutomaticProtocol.Kind.HEARTBEAT;decoded=new AutomaticProtocol.Pulse(number(payload,"sequence"),Boolean.TRUE.equals(payload.get("activated")),number(payload,"stage"),number(payload,"progressBytes"));}
                case "SELECTED_OFFER" -> {
                    need(Boolean.FALSE.equals(payload.get("response")),"selected request direction");kind=AutomaticProtocol.Kind.INSTALL;
                    var bases=new ArrayList<AutomaticRecovery.Basis>();
                    long total=0;for(Object item:list(payload.get("bases")))total+=number(decode(unbase(item),"BASIS").value(),"imageBytes");
                    capacity(total<=bounds.maxSnapshotStagingBytes(),"selected pair capacity");
                    for(Object item:list(payload.get("bases")))bases.add(fetchBasis(decode(unbase(item),"BASIS"),ballot));
                    var selected=AutomaticRecovery.select(manifest,AutomaticRecovery.ballotOf(ballot),bases);
                    need(Arrays.equals(selected.record().bytes(),unbase(payload.get("selected"))),"independent selected pair");decoded=List.copyOf(bases);
                }
                default -> throw outcome(PROTOCOL_MISMATCH,NOT_APPLICABLE);
            }
            long serial=id();var answer=new CompletableFuture<AutomaticProtocol.Message>();Object body=decoded;
            enqueue(()->{incoming.put(serial,answer);protocol.receive(new AutomaticProtocol.Message(serial,kind,text(request,"sender"),local,ballot,false,true,body,null),now());});
            AutomaticProtocol.Message reply;
            try {reply=answer.get(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS);}
            finally {complete(()->incoming.remove(serial));}
            if(!reply.accepted())return reject(request,reply.promised(),reply.payload().toString());
            return switch(kind) {
                case PREPARE -> AutomaticWire.reply(request,"PROMISE",Map.of("nonce",payload.get("nonce"),"basis",b64(((AutomaticRecovery.Basis)reply.payload()).record().bytes())));
                case INSTALL -> {var result=new LinkedHashMap<>(payload);result.put("response",true);yield AutomaticWire.reply(request,"SELECTED_OFFER",result);}
                case ACCEPT -> {var entry=decode(unbase(((Record)decoded).value().get("entry")),"ENTRY");yield AutomaticWire.reply(request,"ACCEPT_ACK",Map.of("index",number(entry.value(),"index"),"entryDigest",entry.digest(),"receipt",reply.payload()));}
                case PROOF -> {var proof=(Record)decoded;yield AutomaticWire.reply(request,"COMMIT_PROOF_ACK",Map.of("index",number(proof.value(),"index"),"proofDigest",sha(proof.bytes()),"receipt",reply.payload()));}
                case HEARTBEAT -> AutomaticWire.reply(request,"HEARTBEAT_ACK",Map.of("sequence",reply.payload(),"provenIndex",(long)view.provenIndex()));
            };
        }catch(Exception error) {
            Throwable cause=error instanceof ExecutionException?error.getCause():error;
            String reason=cause instanceof AutomaticReplicationException e?e.reason().name():"NOT_READY";
            return reject(request,promise,reason);
        }
    }
    private Map<String,Object> reject(Map<String,Object> request,Record promised,String reason) {
        if(!Set.of("NOT_READY","STALE_EPOCH","CONFLICTING_HISTORY","CAPACITY_EXCEEDED","PROTOCOL_MISMATCH","INTEGRITY_FAILURE","STORAGE_FAILURE","CLOSED").contains(reason))reason="NOT_READY";
        return AutomaticWire.reply(request,"REJECT",Map.of("reason",reason,"promised",AutomaticRecovery.ballotOf(promised)));
    }
    @Override public synchronized void close() {
        if(terminated)return;closing=true;
        var stop=new CompletableFuture<Void>();complete(()->{
            try {rejoin.stop();protocol.quiesce();flush();Runnable queued;while((queued=inputs.poll())!=null){queued.run();flush();}stop.complete(null);}
            catch(Throwable error){stop.completeExceptionally(error);}
        });
        try {
            stop.get(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS);transport.close();rejoin.close();network.shutdown();app.shutdown();
            if(!network.awaitTermination(bounds.requestTimeoutMillis()+100L,TimeUnit.MILLISECONDS)||!app.awaitTermination(bounds.requestTimeoutMillis()+100L,TimeUnit.MILLISECONDS))throw outcome(DEADLINE_EXCEEDED,NOT_APPLICABLE);
            application.close();var released=new CompletableFuture<Void>();complete(()->{try{protocol.close();released.complete(null);}catch(Throwable error){released.completeExceptionally(error);}});
            released.get(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS);terminated=true;control.interrupt();control.join(bounds.requestTimeoutMillis());clients.shutdown();
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw outcome(DEADLINE_EXCEEDED,NOT_APPLICABLE);}
        catch(ExecutionException|TimeoutException error){throw AutomaticRecords.failure(DEADLINE_EXCEEDED,"runtime close pending",error);}
    }
}
