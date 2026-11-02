package io.github.patricklfdm.generalsearch.replication;

import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.channels.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BooleanSupplier;
import static io.github.patricklfdm.generalsearch.replication.MembershipContext.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static io.github.patricklfdm.generalsearch.replication.MembershipValidation.require;

/** One TCP attempt per call. The protocol owns identical retries and their original deadline.
 * Identity binding assumes authentic exclusive peers on the trusted private network;
 * this is not TLS authentication and does not establish voter/learner eligibility. */
final class MembershipTransport implements AutoCloseable {
    enum Reason { CAPACITY, CLOSED, DEADLINE, PROTOCOL, IO }
    static final class Failure extends IOException {
        private static final long serialVersionUID=1L;
        final Reason reason;
        Failure(Reason reason,String message,Throwable cause){super(message,cause);this.reason=reason;}
    }
    @FunctionalInterface interface Handler {Decoded handle(MembershipIdentity sender,Decoded request)throws IOException;}
    @FunctionalInterface interface Events {
        Events NONE=(event,request,response)->{};
        void at(String event,Decoded request,Decoded response)throws IOException;
        /** Terminal observation only, after a write/read boundary was observed.
         * This is neither a protocol REJECT nor evidence of remote non-execution. */
        default void failed(boolean outbound,Decoded request,Reason reason)throws IOException {}
    }
    private static final class Attempt {boolean observed;}
    private record Peer(MembershipIdentity identity,InetSocketAddress endpoint,Set<InetAddress> addresses,
                        Semaphore outgoing,Semaphore incoming) {}
    private record Received(Decoded frame,MembershipResources.Lease lease) implements AutoCloseable {
        @Override public void close(){lease.close();}
    }
    record Usage(int outgoing,int incoming,int sockets,boolean closed) {}
    @FunctionalInterface interface Directory {MembershipCapsule current()throws IOException;}
    private final Directory directory;
    private final MembershipLearnerRequest learnerContact;
    private final MembershipDiscovery.Hint learnerPrefix;
    private enum LearnerRead { PREFIX, PROGRESS, JOINING_INTENT }
    private final LearnerRead learnerRead;
    private final String root;
    private final MembershipIdentity local;
    private final ReplicationBounds bounds;
    private final MembershipResources resources;
    private final Handler handler;
    private final Events events;
    private final int maximum;
    private final Semaphore incoming;
    private final ExecutorService workers;
    private final Set<Thread> workerThreads=ConcurrentHashMap.newKeySet();
    private final Set<SocketChannel> channels=ConcurrentHashMap.newKeySet();
    private final AtomicInteger outboundCount=new AtomicInteger(),inboundCount=new AtomicInteger();
    private final ServerSocketChannel server;
    private final Thread acceptor;
    private volatile Map<String,Peer> peers=Map.of();
    private volatile boolean closed;

    MembershipTransport(MembershipCapsule verified,MembershipIdentity local,ReplicationBounds bounds,
            MembershipResources resources,Handler handler,Events events)throws IOException {
        this(verified,local,bounds,resources,handler,events,null,null,null,LearnerRead.PREFIX);
    }
    /** Resolve new permanent reservations only from this exclusive owner's verified catalog. */
    MembershipTransport(MembershipGrantJournal owner,ReplicationBounds bounds,MembershipResources resources,
            Handler handler,Events events)throws IOException {
        this(owner.readOnlyCapsule(),owner.activationIdentity(),bounds,resources,handler,events,owner::readOnlyCapsule,null,null,LearnerRead.PREFIX);
    }
    /** Contact-only client. No listener or locally fabricated voter/catalog is created. */
    static MembershipTransport learner(MembershipLearnerRequest request,ReplicationBounds bounds,
            MembershipResources resources,Events events)throws IOException {
        return new MembershipTransport(null,request.identity(),bounds,resources,(p,r)->{throw new IOException("learner contact has no server");},
                events,null,request,null,LearnerRead.PREFIX);
    }
    static MembershipTransport learnerPrefix(MembershipLearnerRequest request,MembershipDiscovery.Hint hint,ReplicationBounds bounds,
            MembershipResources resources,Events events)throws IOException {
        require(!hint.peer().equals(request.identity()) && request.change().target().contains(hint.peer()),"learner prefix contact route");
        return new MembershipTransport(null,request.identity(),bounds,resources,(p,r)->{throw new IOException("learner contact has no server");},
                events,null,request,hint,LearnerRead.PREFIX);
    }
    static MembershipTransport learnerProgress(MembershipLearnerRequest request,MembershipDiscovery.Hint hint,ReplicationBounds bounds,
            MembershipResources resources,Events events)throws IOException {
        require(!hint.peer().equals(request.identity()) && request.change().target().contains(hint.peer()),"learner progress contact route");
        return new MembershipTransport(null,request.identity(),bounds,resources,(p,r)->{throw new IOException("learner progress has no server");},
                events,null,request,hint,LearnerRead.PROGRESS);
    }
    static MembershipTransport learnerJoiningIntent(MembershipLearnerRequest request,MembershipDiscovery.Hint hint,ReplicationBounds bounds,
            MembershipResources resources,Events events)throws IOException {
        require(!hint.peer().equals(request.identity()) && request.change().target().contains(hint.peer()),"joining intent contact route");
        return new MembershipTransport(null,request.identity(),bounds,resources,(p,r)->{throw new IOException("joining intent contact has no server");},
                events,null,request,hint,LearnerRead.JOINING_INTENT);
    }
    private MembershipTransport(MembershipCapsule verified,MembershipIdentity local,ReplicationBounds bounds,
            MembershipResources resources,Handler handler,Events events,Directory directory,MembershipLearnerRequest learnerContact,MembershipDiscovery.Hint learnerPrefix,LearnerRead learnerRead)throws IOException {
        this.learnerContact=learnerContact;this.learnerRead=learnerRead;this.directory=directory;this.learnerPrefix=learnerPrefix;
        this.root=learnerContact==null?Objects.requireNonNull(verified).context.root:learnerContact.root().manifestDigest();this.local=Objects.requireNonNull(local);
        this.bounds=Objects.requireNonNull(bounds);this.resources=Objects.requireNonNull(resources);
        this.handler=Objects.requireNonNull(handler);this.events=Objects.requireNonNull(events);
        maximum=Math.min(FRAME,bounds.maxFrameBytes());require(maximum>=HEADER,"transport frame bound");
        incoming=new Semaphore((int)Math.min(256,6L*bounds.maxInFlightPerPeer()));
        workers=Executors.newThreadPerTaskExecutor(Thread.ofVirtual().name("gse-membership-io-"+local.nodeId().value()+"-",0).factory());
        ServerSocketChannel opening=null;
        try {
            if(learnerContact==null) {
                learn(verified);opening=ServerSocketChannel.open();opening.configureBlocking(false);
                opening.bind(peers.get(local.nodeId().value()).endpoint());server=opening;
                acceptor=Thread.ofPlatform().daemon().name("gse-membership-listen-"+local.nodeId().value()).start(this::accept);
            }else {
                var routes=new TreeMap<String,MembershipIdentity>();
                for(var identity:learnerContact.change().target())routes.put(identity.nodeId().value(),identity);
                installDirectory(routes);server=null;acceptor=null;
            }
        }catch(IOException|RuntimeException error){if(opening!=null)opening.close();workers.shutdownNow();throw error;}
    }
    /** Only a verified same-root complete catalog can extend the immutable identity directory.
     * Historical peers remain discoverable; directory membership is never a vote. */
    synchronized void learn(MembershipCapsule verified)throws IOException {
        require(learnerContact==null,"learner contact cannot become a voter transport");
        require(!closed && verified.context.root.equals(root),"transport directory root/closed");
        installDirectory(verified.context.identities);
    }
    private void installDirectory(Map<String,MembershipIdentity> registry)throws IOException {
        require(local.equals(registry.get(local.nodeId().value())),"transport local identity absent");
        for(var old:peers.values())require(old.identity.equals(registry.get(old.identity.nodeId().value())),"transport identity reservation lost/changed");
        var next=new TreeMap<String,Peer>();var endpoints=new HashSet<InetSocketAddress>();
        for(var identity:registry.values()) {
            var peer=peers.get(identity.nodeId().value());
            if(peer==null) {
                var resolved=InetAddress.getAllByName(identity.endpoint().host());require(resolved.length>0,"unresolved membership peer");
                for(var address:resolved)require(AutomaticTransport.privateAddress(address),"membership endpoint must be private or loopback");
                peer=new Peer(identity,new InetSocketAddress(resolved[0],identity.endpoint().port()),Set.copyOf(Arrays.asList(resolved)),
                        new Semaphore(bounds.maxInFlightPerPeer()),new Semaphore(bounds.maxInFlightPerPeer()));
            }
            for(var address:peer.addresses)require(endpoints.add(new InetSocketAddress(address,identity.endpoint().port())),"resolved membership endpoint alias");
            next.put(identity.nodeId().value(),peer);
        }
        peers=Map.copyOf(next);
    }
    Usage usage(){return new Usage(outboundCount.get(),inboundCount.get(),channels.size(),closed);}
    /** close() from an I/O callback only cancels. Storage ownership must wait
     * for this predicate on an external closer before releasing its journal. */
    boolean drained(){return closed && (acceptor==null || !acceptor.isAlive()) && workers.isTerminated()
            && channels.isEmpty() && outboundCount.get()==0 && inboundCount.get()==0;}
    private Peer peer(MembershipIdentity identity)throws IOException {
        var peer=peers.get(identity.nodeId().value());
        if(peer==null && directory!=null) {
            // A received sender is only a lookup key. It is never inserted itself.
            learn(directory.current());peer=peers.get(identity.nodeId().value());
        }
        require(peer!=null && peer.identity.equals(identity),"unknown permanent transport identity");return peer;
    }
    private void contactRequest(Decoded request,String kind) {
        if(learnerContact==null)return;
        require(Set.of("CHUNK","TRANSFER_COMMIT","STATUS_PROBE").contains(request.kind())
                && Set.of("SOURCE_OFFER","CHUNK","TRANSFER_COMMIT","STATUS").contains(kind)
                && request.value().get("view").equals(learnerContact.change().expectedConfigurationDigest())
                && request.value().get("ballot").equals(MembershipLearnerDiscovery.correlation(local)),"learner contact read-only correlation");
        if(learnerPrefix!=null)require(request.value().get("recipient").equals(MembershipBootstrapSeed.identity(learnerPrefix.peer())),"learner prefix exact contact");
        if(request.kind().equals("CHUNK") && number(request.value().get("sequence"))==1) {
            String reference=(String)object(request.value().get("payload")).get("digest");
            boolean allowed=learnerPrefix==null?reference.equals(MembershipLearnerDiscovery.reference(learnerContact)):
                    learnerRead==LearnerRead.JOINING_INTENT?reference.equals(MembershipJoiningIntentExport.reference(learnerContact,learnerPrefix.cut())):
                    MembershipLearnerPrefixExport.SCOPES.stream().anyMatch(scope->reference.equals(learnerRead==LearnerRead.PROGRESS?MembershipLearnerProgressAccess.reference(learnerContact,learnerPrefix.cut(),scope):
                            MembershipLearnerPrefixExport.reference(learnerContact,learnerPrefix.cut(),scope)));
            require(allowed,"learner contact reservation reference");
        }
    }
    private MembershipResources.Lease reserve(long size)throws Failure {
        try{return resources.reserve(MembershipResources.Unit.CONTROL,UUID.randomUUID().toString(),size);}
        catch(IllegalArgumentException error){throw new Failure(Reason.CAPACITY,"membership control capacity",error);}
    }
    private void execute(Runnable task) {
        workers.execute(()->{var thread=Thread.currentThread();workerThreads.add(thread);try{task.run();}finally{workerThreads.remove(thread);}});
    }
    CompletableFuture<Decoded> exchange(MembershipIdentity recipient,Decoded request,String responseKind,long originalDeadline) {
        return exchange(recipient,request,responseKind,originalDeadline,()->{});
    }
    /** A revocation check at the actual send boundary, after queueing/connect.
     * It grants no authority itself; typed protocol callers own that decision. */
    CompletableFuture<Decoded> exchange(MembershipIdentity recipient,Decoded request,String responseKind,long originalDeadline,
            MembershipSourcePull.Guard beforeWrite) {
        Objects.requireNonNull(beforeWrite);
        var result=new CompletableFuture<Decoded>();Peer peer=null;MembershipResources.Lease lease=null;boolean acquired=false;
        try {
            if(closed)throw new Failure(Reason.CLOSED,"membership transport closed",null);
            // The caller's deadline can only be shortened by the per-request bound, never renewed in a queue.
            long now=System.nanoTime(),left=originalDeadline-now;
            if(left<=0)throw new Failure(Reason.DEADLINE,"original membership exchange deadline",null);
            long deadline=now+Math.min(left,TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis()));
            peer=peer(recipient);require(!recipient.equals(local),"self transport exchange");
            MembershipWire.envelope(request,root,local,recipient);contactRequest(request,responseKind);
            require(object(CATALOG.get("wire")).containsKey(responseKind) && request.size()<=maximum,"transport request kind/size");
            if(!peer.outgoing.tryAcquire())throw new Failure(Reason.CAPACITY,"membership peer in-flight capacity",null);
            acquired=true;lease=reserve(request.size());byte[] bytes=request.bytes(); // reserve before the copied send buffer
            var owned=lease;var target=peer;outboundCount.incrementAndGet();
            try {
                execute(()->{
                    Decoded reply=null;Throwable failure=null;var attempt=new Attempt();
                    try{reply=send(target,request,bytes,responseKind,deadline,result::isCancelled,beforeWrite,attempt);}
                    catch(Throwable error){failure=classify(error);}
                    finally{owned.close();target.outgoing.release();outboundCount.decrementAndGet();}
                    if(failure!=null && attempt.observed)observeFailure(true,request,failure);
                    // Continuations may immediately submit another request; release first.
                    if(failure==null)result.complete(reply);else result.completeExceptionally(failure);
                });
            }catch(RuntimeException|Error error){outboundCount.decrementAndGet();throw error;}
            return result;
        }catch(Throwable error){
            if(lease!=null)lease.close();
            if(acquired)peer.outgoing.release();
            result.completeExceptionally(classify(error));return result;
        }
    }
    private Throwable classify(Throwable error) {
        if(error instanceof Error)return error;
        if(closed)return new Failure(Reason.CLOSED,"membership transport closed",error);
        if(error instanceof Failure)return error;
        if(error instanceof IllegalArgumentException)return new Failure(Reason.PROTOCOL,"membership frame/context rejected",error);
        return new Failure(Reason.IO,"membership exchange I/O failed",error);
    }
    private void observeFailure(boolean outbound,Decoded request,Throwable failure) {
        if(!(failure instanceof Failure classified))return;
        try{events.failed(outbound,request,classified.reason);}
        catch(Throwable observer){if(observer!=failure)failure.addSuppressed(observer);}
    }
    private Decoded send(Peer peer,Decoded request,byte[] bytes,String kind,long deadline,BooleanSupplier cancelled,
            MembershipSourcePull.Guard beforeWrite,Attempt attempt)throws IOException {
        try(var channel=SocketChannel.open();var selector=Selector.open()) {
            channels.add(channel);
            try {
                check(deadline,cancelled);channel.configureBlocking(false);channel.register(selector,SelectionKey.OP_CONNECT);
                channel.connect(peer.endpoint);while(!channel.finishConnect())ready(selector,SelectionKey.OP_CONNECT,deadline,cancelled);
                attempt.observed=true;events.at("BEFORE_REQUEST_WRITE",request,null);beforeWrite.check();check(deadline,cancelled);
                transfer(channel,selector,ByteBuffer.wrap(bytes),true,deadline,cancelled);
                try(var response=read(channel,selector,deadline,cancelled)) {
                    MembershipWire.envelope(response.frame,root,peer.identity,local);MembershipWire.correlated(request,response.frame,kind);
                    events.at("AFTER_RESPONSE_READ",request,response.frame);check(deadline,cancelled);return response.frame;
                }
            }finally{channels.remove(channel);}
        }
    }
    private void accept() {
        try(var selector=Selector.open()) {
            server.register(selector,SelectionKey.OP_ACCEPT);
            while(!closed) {
                selector.select(100);selector.selectedKeys().clear();SocketChannel channel;
                while(!closed && (channel=server.accept())!=null) {
                    if(!incoming.tryAcquire()){channel.close();continue;}
                    channels.add(channel);inboundCount.incrementAndGet();var accepted=channel;
                    long deadline=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis());
                    try{execute(()->serve(accepted,deadline));}
                    catch(RuntimeException error){channels.remove(channel);inboundCount.decrementAndGet();incoming.release();channel.close();if(!closed)throw error;}
                }
            }
        }catch(IOException|RuntimeException error){if(!closed)stop();}
    }
    private void serve(SocketChannel channel,long deadline) {
        Peer admitted=null;
        try(channel;var selector=Selector.open()) {
            channel.configureBlocking(false);channel.register(selector,SelectionKey.OP_READ);
            try(var received=read(channel,selector,deadline,()->false)) {
                var request=received.frame;var sender=identity(object(request.value().get("sender")));var peer=peer(sender);
                MembershipWire.envelope(request,root,sender,local);
                require(peer.addresses.contains(((InetSocketAddress)channel.getRemoteAddress()).getAddress()),"transport sender address binding");
                if(!peer.incoming.tryAcquire())throw new Failure(Reason.CAPACITY,"membership inbound peer capacity",null);admitted=peer;
                try {
                    events.at("AFTER_REQUEST_READ",request,null);check(deadline,()->false);
                    var response=Objects.requireNonNull(handler.handle(sender,request),"membership handler response");
                    MembershipWire.envelope(response,root,local,sender);MembershipWire.correlated(request,response,response.kind());
                    require(response.size()<=maximum,"transport response frame size");
                    try(var lease=reserve(response.size())) {
                        events.at("BEFORE_RESPONSE_WRITE",request,response);
                        transfer(channel,selector,ByteBuffer.wrap(response.bytes()),true,deadline,()->false);
                    }
                }catch(IOException|RuntimeException error){
                    // Publish the handler's terminal observation before closing
                    // this socket can unblock an identical caller retry.
                    observeFailure(false,request,classify(error));throw error;
                }
            }
        }catch(IOException|RuntimeException ignored){
            // No ACK is manufactured. The protocol can return a classified REJECT;
            // malformed frames, I/O failures and thrown handlers close this attempt.
        }finally{if(admitted!=null)admitted.incoming.release();channels.remove(channel);inboundCount.decrementAndGet();incoming.release();}
    }
    private Received read(SocketChannel channel,Selector selector,long deadline,BooleanSupplier cancelled)throws IOException {
        var lease=reserve(HEADER);
        try {
            byte[] header=new byte[HEADER];transfer(channel,selector,ByteBuffer.wrap(header),false,deadline,cancelled);
            int length=MembershipWire.bodyLength(header,maximum);
            try{lease.reserveControl(HEADER+(long)length);}catch(IllegalArgumentException error){throw new Failure(Reason.CAPACITY,"membership receive capacity",error);}
            byte[] bytes=Arrays.copyOf(header,HEADER+length);
            transfer(channel,selector,ByteBuffer.wrap(bytes,HEADER,length),false,deadline,cancelled);
            return new Received(MembershipWire.decode(bytes,maximum),lease);
        }catch(IOException|RuntimeException|Error error){lease.close();throw error;}
    }
    private void check(long deadline,BooleanSupplier cancelled)throws Failure {
        if(closed)throw new Failure(Reason.CLOSED,"membership transport closed",null);
        if(cancelled.getAsBoolean() || Thread.currentThread().isInterrupted())throw new Failure(Reason.IO,"membership exchange interrupted",null);
        if(deadline-System.nanoTime()<=0)throw new Failure(Reason.DEADLINE,"membership exchange deadline",null);
    }
    private void transfer(SocketChannel channel,Selector selector,ByteBuffer buffer,boolean write,long deadline,BooleanSupplier cancelled)throws IOException {
        while(buffer.hasRemaining()) {
            check(deadline,cancelled);int count=write?channel.write(buffer):channel.read(buffer);
            if(count<0)throw new EOFException("incomplete membership wire frame");
            if(count==0)ready(selector,write?SelectionKey.OP_WRITE:SelectionKey.OP_READ,deadline,cancelled);
        }
    }
    private void ready(Selector selector,int operation,long deadline,BooleanSupplier cancelled)throws IOException {
        check(deadline,cancelled);for(var key:selector.keys())key.interestOps(operation);
        selector.select(Math.max(1,Math.min(100,TimeUnit.NANOSECONDS.toMillis(deadline-System.nanoTime()))));selector.selectedKeys().clear();
    }
    private void stop() {
        closed=true;try{if(server!=null)server.close();}catch(IOException ignored){}
        for(var channel:channels)try{channel.close();}catch(IOException ignored){}
        workers.shutdownNow();
    }
    @Override public void close() {
        stop();if(workerThreads.contains(Thread.currentThread()))return; // a completion callback may initiate close
        try {
            if(acceptor!=null)acceptor.join(bounds.requestTimeoutMillis());
            require((acceptor==null || !acceptor.isAlive()) && workers.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"membership transport close timeout");
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException("membership transport close interrupted",error);}
    }
}
