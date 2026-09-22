package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.ByteBuffer;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;

/** Automatic-only bounded NIO exchanges; inbound waits run outside the protocol dispatcher. */
final class AutomaticTransport implements AutoCloseable {
    interface Events {
        Events NONE = (barrier, request, response) -> { };
        void at(String barrier, Map<String, Object> request, Map<String, Object> response) throws IOException;
        /** Internal observation only. The token identifies one reservation, including exact-request retries. */
        default void accounting(String event, Map<String,Object> request, Object token, int bytes) { }
    }
    private final AutomaticRecords.Record manifest;
    private final String local;
    private final ReplicationBounds bounds;
    private final Map<String, InetSocketAddress> addresses = new java.util.HashMap<>();
    private final Map<String, Semaphore> outbound = new java.util.HashMap<>();
    private final Map<String, java.util.concurrent.ThreadPoolExecutor> senders = new java.util.HashMap<>();
    private final Set<Thread> senderThreads = ConcurrentHashMap.newKeySet();
    private final java.util.concurrent.atomic.AtomicLong queuedBytes = new java.util.concurrent.atomic.AtomicLong();
    private final Semaphore inbound;
    private final Set<SocketChannel> channels = ConcurrentHashMap.newKeySet();
    private final ExecutorService workers = Executors.newVirtualThreadPerTaskExecutor();
    private final ServerSocketChannel server;
    private final Thread acceptor;
    private final Function<Map<String, Object>, Map<String, Object>> handler;
    private final Events events;
    private volatile boolean closed;

    AutomaticTransport(AutomaticRecords.Record manifest, String local, ReplicationBounds bounds,
                     Function<Map<String, Object>, Map<String, Object>> handler) {
        this(manifest, local, bounds, handler, Events.NONE);
    }

    AutomaticTransport(AutomaticRecords.Record manifest, String local, ReplicationBounds bounds,
                     Function<Map<String, Object>, Map<String, Object>> handler, Events events) {
        this.manifest = manifest; this.local = local; this.bounds = bounds; this.handler = handler;
        this.events = events;
        inbound = new Semaphore(8);
        ServerSocketChannel opening = null;
        try {
            for (Object row : AutomaticRecords.list(manifest.value().get("members"))) {
                var member = AutomaticRecords.object(row);
                String peer = AutomaticRecords.text(member,"node");
                InetAddress[] resolved = InetAddress.getAllByName(AutomaticRecords.text(member,"host"));
                require(resolved.length > 0, PROTOCOL_MISMATCH, "unresolved replica endpoint");
                for (var address : resolved) require(privateAddress(address), PROTOCOL_MISMATCH, "replication endpoints must be private or loopback");
                addresses.put(peer, new InetSocketAddress(resolved[0], (int)AutomaticRecords.number(member,"port")));
                outbound.put(peer, new Semaphore(2));
                if (!peer.equals(local)) senders.put(peer, new java.util.concurrent.ThreadPoolExecutor(
                        2, 2, 0, TimeUnit.MILLISECONDS, new java.util.concurrent.ArrayBlockingQueue<>(2),
                        task -> {
                            Thread thread = Thread.ofPlatform().daemon().name("gse-automatic-send-" + local + "-" + peer).unstarted(task);
                            senderThreads.add(thread); return thread;
                        }));
            }
            require(addresses.containsKey(local), PROTOCOL_MISMATCH, "unknown local endpoint");
            require(new java.util.HashSet<>(addresses.values()).size() == 3, PROTOCOL_MISMATCH, "resolved voter endpoints overlap");
            opening = ServerSocketChannel.open();
            opening.configureBlocking(false);
            opening.bind(addresses.get(local));
            server = opening;
            acceptor = Thread.ofPlatform().daemon().name("gse-automatic-accept-" + local).start(this::accept);
        } catch (IOException | RuntimeException error) {
            if (opening != null) try { opening.close(); } catch (IOException suppressed) { error.addSuppressed(suppressed); }
            workers.shutdownNow();
            senders.values().forEach(java.util.concurrent.ThreadPoolExecutor::shutdown);
            if (error instanceof ReplicationException classified) throw classified;
            throw failure(STORAGE_FAILURE, "cannot bind replica transport", error);
        }
    }

    static boolean privateAddress(InetAddress address) {
        byte[] bytes = address.getAddress();
        return !address.isAnyLocalAddress() && !address.isMulticastAddress()
                && (address.isLoopbackAddress() || address.isSiteLocalAddress()
                || bytes.length == 16 && (bytes[0] & 0xfe) == 0xfc);
    }

    CompletableFuture<Map<String, Object>> exchange(String peer, Map<String, Object> request) {
        if (closed) return CompletableFuture.failedFuture(new ReplicationException(CLOSED, "transport closed"));
        Semaphore capacity = outbound.get(peer);
        if (capacity == null || peer.equals(local)) return CompletableFuture.failedFuture(new ReplicationException(PROTOCOL_MISMATCH, "invalid peer"));
        if (!capacity.tryAcquire()) {
            events.accounting("OUTBOUND_REJECTED",request,null,0);
            return CompletableFuture.failedFuture(new ReplicationException(CAPACITY_EXCEEDED, "peer in-flight limit reached"));
        }
        var result = new CompletableFuture<Map<String, Object>>();
        byte[] bytes;
        try { bytes = AutomaticWire.encode(request, manifest, bounds.maxFrameBytes()); }
        catch (RuntimeException error) { capacity.release(); return CompletableFuture.failedFuture(error); }
        if (queuedBytes.addAndGet(bytes.length) > (long) bounds.maxFrameBytes() * 4) {
            queuedBytes.addAndGet(-bytes.length); capacity.release();
            return CompletableFuture.failedFuture(new ReplicationException(CAPACITY_EXCEEDED, "outbound byte budget exhausted"));
        }
        long deadline = deadline();
        Map<String, Object> expected = java.util.Collections.unmodifiableMap(new java.util.LinkedHashMap<>(request));
        try {
            events.accounting("OUTBOUND_ADMITTED",expected,result,bytes.length);
            senders.get(peer).execute(() -> {
                try {
                    // The deadline includes queue time; two admitted lanes prevent reverse basis fetch from waiting behind itself.
                    require(System.nanoTime() < deadline, QUORUM_UNAVAILABLE, "peer request expired in queue");
                    IOException last = null;
                    for (int attempt = 0; attempt <= bounds.maxRetryAttempts(); attempt++) {
                        if (closed) throw new ReplicationException(CLOSED, "transport closed");
                        try (var channel = SocketChannel.open(); var selector = Selector.open()) {
                            channels.add(channel);
                            try {
                                require(!closed, CLOSED, "transport closed");
                                channel.configureBlocking(false);
                                channel.register(selector, SelectionKey.OP_CONNECT);
                                channel.connect(addresses.get(peer));
                                while (!channel.finishConnect()) ready(selector, SelectionKey.OP_CONNECT, deadline);
                                events.at("BEFORE_REQUEST_WRITE", expected, Map.of());
                                transfer(channel, selector, ByteBuffer.wrap(bytes), true, deadline);
                                Map<String, Object> response = read(channel, selector, deadline);
                                AutomaticRecords.need(local.equals(response.get("recipient")), "wrong response endpoint");
                                AutomaticWire.correlated(expected,response);
                                for (String field : java.util.List.of("epoch", "incarnationId", "traceId", "eventSequence"))
                                    require(expected.get(field).equals(response.get(field)), PROTOCOL_MISMATCH, "uncorrelated response: " + field);
                                require(AutomaticRecords.text(response, "sender").equals(peer), PROTOCOL_MISMATCH, "wrong response voter");
                                events.at("AFTER_RESPONSE_READ", expected, response);
                                result.complete(response);
                                return;
                            } finally { channels.remove(channel); }
                        } catch (IOException error) {
                            last = error;
                            if (attempt == bounds.maxRetryAttempts() || System.nanoTime() >= deadline) break;
                            long left = deadline - System.nanoTime();
                            if (left <= 0) break;
                            TimeUnit.NANOSECONDS.sleep(Math.min(left, TimeUnit.MILLISECONDS.toNanos(bounds.retryBackoffMillis())));
                        }
                    }
                    throw failure(QUORUM_UNAVAILABLE, "peer request failed or timed out", last);
                } catch (Throwable error) {
                    if (error instanceof InterruptedException) Thread.currentThread().interrupt();
                    result.completeExceptionally(closed ? failure(CLOSED, "transport closed", error) : error);
                } finally { releaseOutbound(expected,result,bytes.length,capacity); }
            });
        } catch (RuntimeException error) { releaseOutbound(expected,result,bytes.length,capacity); result.completeExceptionally(error); }
        return result;
    }

    private void releaseOutbound(Map<String,Object> request,Object token,int bytes,Semaphore capacity) {
        try { events.accounting("OUTBOUND_RELEASED",request,token,bytes); }
        finally { queuedBytes.addAndGet(-bytes); capacity.release(); }
    }

    private void releaseInbound(SocketChannel channel) {
        try { events.accounting("INBOUND_RELEASED",Map.of(),channel,0); }
        finally { channels.remove(channel); inbound.release(); }
    }

    private void accept() {
        try (var selector = Selector.open()) {
            server.register(selector, SelectionKey.OP_ACCEPT);
            while (!closed) {
                selector.select(100);
                selector.selectedKeys().clear();
                SocketChannel channel;
                while ((channel = server.accept()) != null) {
                    if (!inbound.tryAcquire()) { channel.close(); events.accounting("INBOUND_REJECTED",Map.of(),null,0); continue; }
                    channels.add(channel);
                    SocketChannel accepted = channel;
                    try {
                        events.accounting("INBOUND_ADMITTED",Map.of(),accepted,0);
                        workers.execute(() -> serve(accepted));
                    }
                    catch (RuntimeException error) {
                        try { releaseInbound(channel); } finally { channel.close(); }
                        if (!closed) throw error;
                    }
                }
            }
        } catch (IOException | RuntimeException error) {
            if (!closed) stop();
        }
    }

    private void serve(SocketChannel channel) {
        try (channel; var selector = Selector.open()) {
            channel.configureBlocking(false);
            channel.register(selector, SelectionKey.OP_READ);
            long deadline = deadline();
            Map<String, Object> request = read(channel, selector, deadline);
            AutomaticRecords.need(local.equals(request.get("recipient")), "wrong request endpoint");
            Map<String, Object> response = handler.apply(request);
            events.at("BEFORE_RESPONSE_WRITE", request, response);
            transfer(channel, selector, ByteBuffer.wrap(AutomaticWire.encode(response, manifest, bounds.maxFrameBytes())), true, deadline);
        } catch (IOException | RuntimeException ignored) {
            // Malformed/uncorrelated frames close the connection; no durable success is manufactured.
        } finally { releaseInbound(channel); }
    }

    private Map<String, Object> read(SocketChannel channel, Selector selector, long deadline) throws IOException {
        byte[] header = new byte[HEADER_BYTES];
        transfer(channel, selector, ByteBuffer.wrap(header), false, deadline);
        int length = AutomaticWire.bodyLength(header, bounds.maxFrameBytes());
        byte[] frame = new byte[HEADER_BYTES + length];
        System.arraycopy(header, 0, frame, 0, HEADER_BYTES);
        transfer(channel, selector, ByteBuffer.wrap(frame, HEADER_BYTES, length), false, deadline);
        return AutomaticWire.decode(frame, manifest, bounds.maxFrameBytes());
    }

    private static void transfer(SocketChannel channel, Selector selector, ByteBuffer buffer, boolean write, long deadline) throws IOException {
        while (buffer.hasRemaining()) {
            if (Thread.currentThread().isInterrupted() || System.nanoTime() >= deadline) throw new IOException("replica exchange timed out/interrupted");
            int count = write ? channel.write(buffer) : channel.read(buffer);
            if (count < 0) throw new IOException("peer closed an incomplete frame");
            if (count == 0) ready(selector, write ? SelectionKey.OP_WRITE : SelectionKey.OP_READ, deadline);
        }
    }
    private static void ready(Selector selector, int operation, long deadline) throws IOException {
        if (Thread.currentThread().isInterrupted()) throw new IOException("replica exchange interrupted");
        long left = deadline - System.nanoTime();
        if (left <= 0) throw new IOException("replica exchange deadline expired");
        for (SelectionKey key : selector.keys()) key.interestOps(operation);
        selector.select(Math.max(1, Math.min(100, TimeUnit.NANOSECONDS.toMillis(left))));
        selector.selectedKeys().clear();
    }
    private long deadline() { return System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(bounds.requestTimeoutMillis()); }
    private void closeChannels() {
        for (var channel : channels) try { channel.close(); } catch (IOException ignored) { }
        try { server.close(); } catch (IOException ignored) { }
    }
    private void stop() {
        closed = true;
        closeChannels();
        senders.values().forEach(java.util.concurrent.ThreadPoolExecutor::shutdown);
        for (Thread sender : senderThreads) if (sender != Thread.currentThread()) sender.interrupt();
        workers.shutdownNow();
    }
    @Override public void close() {
        stop();
        try {
            acceptor.join(bounds.requestTimeoutMillis());
            require(!acceptor.isAlive(), CLOSED, "acceptor did not terminate");
            require(workers.awaitTermination(bounds.requestTimeoutMillis(), TimeUnit.MILLISECONDS), CLOSED, "transport did not terminate");
            for (var sender : senders.entrySet())
                require(sender.getValue().awaitTermination(bounds.requestTimeoutMillis() + 100L, TimeUnit.MILLISECONDS),
                    CLOSED, "peer sender did not terminate");
        } catch (InterruptedException error) { Thread.currentThread().interrupt(); throw failure(CLOSED, "transport close interrupted", error); }
    }
}
