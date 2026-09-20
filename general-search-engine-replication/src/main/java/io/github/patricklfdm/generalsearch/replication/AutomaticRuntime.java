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
        this.events=events;
        bounds=config.bounds();policy=config.leadershipPolicy();local=config.localNodeId().value();manifest=decode(manifestBytes,"MANIFEST");
        need(config.groupId().value().toString().equals(manifest.value().get("groupId"))&&config.configurationId().equals(manifest.value().get("configurationId")),"runtime group configuration");
        need(config.members().stream().map(m->Map.of("node",m.nodeId().value(),"host",m.endpoint().host(),"port",(long)m.endpoint().port())).toList().equals(manifest.value().get("members")),"runtime members/order");
        store=AutomaticStore.open(config.replicaDirectory(),manifestBytes,local,bounds,faults);
        AutomaticApplication<K,T> opening=null;AutomaticTransport listening=null;
        try {
            need(store.leadershipPolicy().equals(policy),"runtime policy differs from seal");
            opening=new AutomaticApplication<>(captured,config.materialization(),bounds);opening.validate(manifest,config.materialization());application=opening;
            protocol=new AutomaticProtocol(store,()->ThreadLocalRandom.current().nextLong(),UUID::randomUUID);
            promise=protocol.promise();view=protocol.view();
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
    // Test/internal inspection only; this is deliberately not a public strong-read implementation.
    <R> CompletableFuture<R> inspectLocal(Function<SearchEngine<K,T>,R> action) {
        var result=new CompletableFuture<R>();
        try {app.execute(()->{try {result.complete(application.readLocal(action));}catch(Throwable e){result.completeExceptionally(e);}});}
        catch(RejectedExecutionException error) {result.completeExceptionally(error);}return result;
    }
    CompletableFuture<Long> submit(int operation,Function<ReplicaApplication<K,T>,byte[]> encoder) {
        var result=new CompletableFuture<Long>();
        if(closing||failure!=null||!submission.tryAcquire()) {result.completeExceptionally(outcome(closing?CLOSED:CAPACITY_EXCEEDED,NOT_SUBMITTED));return result;}
        long request=id(),deadline=now()+policy.operationTimeoutMillis();
        try {enqueue(()->{
            if(view.state()!=AutomaticReplicationState.LEADER_READY) {finish(result,null,outcome(NOT_READY,NOT_SUBMITTED));return;}
            Record expected=promise;int cut=view.publishedIndex();
            try {app.execute(()->{
                byte[] payload=null;Throwable error=null;
                try {need(operation>=1&&operation<=9,"application operation");payload=Objects.requireNonNull(encoder.apply(application.encoder())).clone();application.stage(operation,payload);}
                catch(Throwable e){error=e;}
                byte[] bytes=payload;Throwable rejected=error;
                complete(()->{
                    if(rejected!=null) {finish(result,null,rejected);return;}
                    if(closing||now()>=deadline||!Arrays.equals(expected.bytes(),promise.bytes())||view.state()!=AutomaticReplicationState.LEADER_READY||view.publishedIndex()!=cut) {
                        finish(result,null,outcome(NOT_READY,NOT_SUBMITTED));return;
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
        clients.execute(()->{try {if(error==null)future.complete(value);else future.completeExceptionally(error);}finally{submission.release();}});
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
        for(var action:protocol.drain()) {
            if(action instanceof AutomaticProtocol.Send send) {
                var message=send.message();
                if(message.response()) {var future=incoming.remove(message.id());if(future!=null)future.complete(message);}
                else try {network.execute(()->{
                    try {var reply=exchange(message);complete(()->protocol.receive(reply,now()));}
                    catch(Throwable error){lastExchangeFailure=error;complete(()->protocol.transportFailed(message.id(),now()));}
                });}catch(RejectedExecutionException error){protocol.transportFailed(message.id(),now());}
            }else if(action instanceof AutomaticProtocol.Reconstruct rebuild) {
                app.execute(()->{byte[] image=null;Throwable failure=null;try{image=application.reconstruct(rebuild.replay());}catch(Throwable e){failure=e;}
                    byte[] value=image;Throwable error=failure;complete(()->protocol.reconstructed(rebuild.id(),value,error,now()));});
            }else if(action instanceof AutomaticProtocol.Publish publish) {
                app.execute(()->{Throwable failure=null;try{application.publish(publish.snapshot());events.at("PUBLISHED",Map.of("ballot",b64(publish.ballot().bytes()),"snapshot",b64(publish.snapshot().bytes())));}catch(Throwable e){failure=e;}
                    Throwable error=failure;complete(()->protocol.published(publish.id(),error,now()));});
            }else if(action instanceof AutomaticProtocol.Completed done) {
                var future=requests.remove(done.request());if(future!=null)finish(future,done.index(),done.reason()==null?null:outcome(done.reason(),done.outcome()));
            }
        }
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
