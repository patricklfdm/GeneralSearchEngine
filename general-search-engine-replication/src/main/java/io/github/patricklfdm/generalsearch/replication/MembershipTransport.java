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
    }
    private record Peer(MembershipIdentity identity,InetSocketAddress endpoint,Set<InetAddress> addresses,
                        Semaphore outgoing,Semaphore incoming) {}
    private record Received(Decoded frame,MembershipResources.Lease lease) implements AutoCloseable {
        @Override public void close(){lease.close();}
    }
    record Usage(int outgoing,int incoming,int sockets,boolean closed) {}
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
        this.root=Objects.requireNonNull(verified).context.root;this.local=Objects.requireNonNull(local);
        this.bounds=Objects.requireNonNull(bounds);this.resources=Objects.requireNonNull(resources);
        this.handler=Objects.requireNonNull(handler);this.events=Objects.requireNonNull(events);
        maximum=Math.min(FRAME,bounds.maxFrameBytes());require(maximum>=HEADER,"transport frame bound");
        incoming=new Semaphore((int)Math.min(256,6L*bounds.maxInFlightPerPeer()));
        workers=Executors.newThreadPerTaskExecutor(Thread.ofVirtual().name("gse-membership-io-"+local.nodeId().value()+"-",0).factory());
        ServerSocketChannel opening=null;
        try {
            learn(verified);opening=ServerSocketChannel.open();opening.configureBlocking(false);
            opening.bind(peers.get(local.nodeId().value()).endpoint());server=opening;
            acceptor=Thread.ofPlatform().daemon().name("gse-membership-listen-"+local.nodeId().value()).start(this::accept);
        }catch(IOException|RuntimeException error){if(opening!=null)opening.close();workers.shutdownNow();throw error;}
    }
    /** Only a verified same-root complete catalog can extend the immutable identity directory.
     * Historical peers remain discoverable; directory membership is never a vote. */
    synchronized void learn(MembershipCapsule verified)throws IOException {
        require(!closed && verified.context.root.equals(root),"transport directory root/closed");
        var registry=verified.context.identities;require(local.equals(registry.get(local.nodeId().value())),"transport local identity absent");
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
    private Peer peer(MembershipIdentity identity) {
        var peer=peers.get(identity.nodeId().value());require(peer!=null && peer.identity.equals(identity),"unknown permanent transport identity");return peer;
    }
    private MembershipResources.Lease reserve(long size)throws Failure {
        try{return resources.reserve(MembershipResources.Unit.CONTROL,UUID.randomUUID().toString(),size);}
        catch(IllegalArgumentException error){throw new Failure(Reason.CAPACITY,"membership control capacity",error);}
    }
    private void execute(Runnable task) {
        workers.execute(()->{var thread=Thread.currentThread();workerThreads.add(thread);try{task.run();}finally{workerThreads.remove(thread);}});
    }
    CompletableFuture<Decoded> exchange(MembershipIdentity recipient,Decoded request,String responseKind,long originalDeadline) {
        var result=new CompletableFuture<Decoded>();Peer peer;MembershipResources.Lease lease=null;boolean acquired=false;
        try {
            if(closed)throw new Failure(Reason.CLOSED,"membership transport closed",null);
            // The caller's deadline can only be shortened by the per-request bound, never renewed in a queue.
            long now=System.nanoTime(),left=originalDeadline-now;
            if(left<=0)throw new Failure(Reason.DEADLINE,"original membership exchange deadline",null);
            long deadline=now+Math.min(left,TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis()));
            peer=peer(recipient);require(!recipient.equals(local),"self transport exchange");
            MembershipWire.envelope(request,root,local,recipient);
            require(object(CATALOG.get("wire")).containsKey(responseKind) && request.size()<=maximum,"transport request kind/size");
            if(!peer.outgoing.tryAcquire())throw new Failure(Reason.CAPACITY,"membership peer in-flight capacity",null);
            acquired=true;lease=reserve(request.size());byte[] bytes=request.bytes(); // reserve before the copied send buffer
            var owned=lease;outboundCount.incrementAndGet();
            try {
                execute(()->{
                    Decoded reply=null;Throwable failure=null;
                    try{reply=send(peer,request,bytes,responseKind,deadline,result::isCancelled);}
                    catch(Throwable error){failure=classify(error);}
                    finally{owned.close();peer.outgoing.release();outboundCount.decrementAndGet();}
                    // Continuations may immediately submit another request; release first.
                    if(failure==null)result.complete(reply);else result.completeExceptionally(failure);
                });
            }catch(RuntimeException|Error error){outboundCount.decrementAndGet();throw error;}
            return result;
        }catch(Throwable error){
            if(lease!=null)lease.close();
            if(acquired)peer(recipient).outgoing.release();
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
    private Decoded send(Peer peer,Decoded request,byte[] bytes,String kind,long deadline,BooleanSupplier cancelled)throws IOException {
        try(var channel=SocketChannel.open();var selector=Selector.open()) {
            channels.add(channel);
            try {
                check(deadline,cancelled);channel.configureBlocking(false);channel.register(selector,SelectionKey.OP_CONNECT);
                channel.connect(peer.endpoint);while(!channel.finishConnect())ready(selector,SelectionKey.OP_CONNECT,deadline,cancelled);
                events.at("BEFORE_REQUEST_WRITE",request,null);transfer(channel,selector,ByteBuffer.wrap(bytes),true,deadline,cancelled);
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
                events.at("AFTER_REQUEST_READ",request,null);check(deadline,()->false);
                var response=Objects.requireNonNull(handler.handle(sender,request),"membership handler response");
                MembershipWire.envelope(response,root,local,sender);MembershipWire.correlated(request,response,response.kind());
                require(response.size()<=maximum,"transport response frame size");
                try(var lease=reserve(response.size())) {
                    events.at("BEFORE_RESPONSE_WRITE",request,response);
                    transfer(channel,selector,ByteBuffer.wrap(response.bytes()),true,deadline,()->false);
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
        closed=true;try{server.close();}catch(IOException ignored){}
        for(var channel:channels)try{channel.close();}catch(IOException ignored){}
        workers.shutdownNow();
    }
    @Override public void close() {
        stop();if(workerThreads.contains(Thread.currentThread()))return; // a completion callback may initiate close
        try {
            acceptor.join(bounds.requestTimeoutMillis());
            require(!acceptor.isAlive() && workers.awaitTermination(bounds.requestTimeoutMillis(),TimeUnit.MILLISECONDS),"membership transport close timeout");
        }catch(InterruptedException error){Thread.currentThread().interrupt();throw new IllegalStateException("membership transport close interrupted",error);}
    }
}
