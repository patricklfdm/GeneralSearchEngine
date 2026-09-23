package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.*;
import static org.junit.jupiter.api.Assertions.*;

import java.io.IOException;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.file.Path;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class V50NetworkHardeningTest {
    @TempDir Path temporary;

    @ParameterizedTest
    @ValueSource(strings = {"ACTIVATE_EPOCH", "APPEND", "COMMIT_PROOF", "SNAPSHOT_OFFER", "SNAPSHOT_CHUNK", "SNAPSHOT_INSTALL"})
    void lostDurableResponsesRetryIdenticalBytesWithoutDuplicateApplication(String type) throws Exception {
        var armed = new AtomicBoolean(type.equals("ACTIVATE_EPOCH"));
        var attempts = new ConcurrentHashMap<String, AtomicInteger>();
        var bytes = new ConcurrentHashMap<String, String>();
        try (var group = new Group(temporary, bounds(3000, 8), ReplicaNode.Events.NONE, local -> (barrier, request, response) -> {
            if (local != 0 && armed.get() && barrier.equals("BEFORE_RESPONSE_WRITE") && request.get("type").equals(type)) {
                String key = local + ":" + request.get("traceId");
                String digest = sha256(ReplicaWire.encode(request, BOUNDS.maxFrameBytes()));
                String previous = bytes.putIfAbsent(key, digest); if (previous != null) assertEquals(previous, digest);
                if (attempts.computeIfAbsent(key, ignored -> new AtomicInteger()).incrementAndGet() == 1)
                    throw new IOException("deterministic disconnect after durable processing");
            }
        })) {
            group.leader().activate().get(15, TimeUnit.SECONDS); armed.set(true);
            group.add(new Document(1, "shared")).get(15, TimeUnit.SECONDS);
            if (type.startsWith("SNAPSHOT_")) group.leader().checkpoint().get(15, TimeUnit.SECONDS);
            V50LeaderPathTest.await(() -> !attempts.isEmpty() && attempts.values().stream().allMatch(count -> count.get() == 2));
            V50LeaderPathTest.await(() -> group.nodes.stream().allMatch(node -> node.status().applicationSequence() == 1));
            assertEquals(2, group.leader().status().appliedIndex());
            for (var app : group.applications) assertEquals(List.of(new Document(1, "shared")), app.read(engine -> engine.search(document -> true)));
        }
    }

    @ParameterizedTest
    @ValueSource(booleans = {false, true})
    void retryExhaustionCannotPublishAndRecoveryRemovesOnlyUnprovenTail(boolean delayedActivation) throws Exception {
        var armed = new AtomicBoolean(); var attempts = List.of(new AtomicInteger(), new AtomicInteger(), new AtomicInteger());
        var activationEntered = new CountDownLatch(1); var releaseActivation = new CountDownLatch(1);
        var delayedAfterArming = new AtomicBoolean();
        var requestBytes = new ConcurrentHashMap<Integer, String>();
        try (var group = new Group(temporary, bounds(1500, 8), ReplicaNode.Events.NONE, local -> (barrier, request, response) -> {
            if (local != 0 && barrier.equals("BEFORE_RESPONSE_WRITE") && request.get("type").equals("APPEND")) {
                var entry = appendEntry(request);
                if (delayedActivation && local == 2 && entry.index() == 1 && entry.operation().equals("NO_OP")) {
                    activationEntered.countDown();
                    try { if (!releaseActivation.await(5, TimeUnit.SECONDS)) throw new IOException("activation release missing"); }
                    catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new IOException(error); }
                    delayedAfterArming.set(armed.get());
                }
                // Activation needs only one remote ACK; the other NO_OP can
                // finish after arming. Exhaust this ADD exchange, not that old one.
                if (armed.get() && entry.index() == 2 && entry.operation().equals("ADD")) {
                    String digest = sha256(ReplicaWire.encode(request, BOUNDS.maxFrameBytes()));
                    String previous = requestBytes.putIfAbsent(local, digest);
                    if (previous != null) assertEquals(previous, digest, "retry changed request identity or bytes");
                    attempts.get(local).incrementAndGet(); throw new IOException("all target ADD ACKs disconnected");
                }
            }
        })) {
            group.leader().activate().get(10, TimeUnit.SECONDS); armed.set(true);
            if (delayedActivation) assertTrue(activationEntered.await(5, TimeUnit.SECONDS));
            releaseActivation.countDown();
            V50LeaderPathTest.rejected(ReplicationException.Reason.QUORUM_UNAVAILABLE, group.add(new Document(1, "must remain hidden")));
            if (delayedActivation) assertTrue(delayedAfterArming.get(), "exercise activation ACK after the fault was armed");
            assertEquals(0, group.leader().status().applicationSequence());
            assertNull(group.leader().read(engine -> engine.get(1)));
            for (int i : List.of(1, 2)) assertEquals(BOUNDS.maxRetryAttempts() + 1, attempts.get(i).get());
            armed.set(false); group.leader().activate().get(10, TimeUnit.SECONDS);
            assertNull(group.leader().read(engine -> engine.get(1)));
            group.add(new Document(2, "shared")).get(10, TimeUnit.SECONDS);
            assertEquals(1, group.leader().status().applicationSequence());
        }
    }

    @Test
    void slowFollowerDoesNotBlockHealthyQuorumAndCatchesUpAfterRelease() throws Exception {
        var armed = new AtomicBoolean(); var entered = new CountDownLatch(1); var release = new CountDownLatch(1);
        var group = new Group(temporary, bounds(1200, 8), ReplicaNode.Events.NONE, local -> (barrier, request, response) -> {
            if (local == 2 && armed.get() && barrier.equals("BEFORE_RESPONSE_WRITE") && request.get("type").equals("APPEND")) {
                entered.countDown();
                try { if (!release.await(10, TimeUnit.SECONDS)) throw new IOException("test release missing"); }
                catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new IOException(error); }
            }
        });
        try {
            group.leader().activate().get(10, TimeUnit.SECONDS); armed.set(true);
            for (int i = 1; i <= 10; i++) group.add(new Document(i, "shared")).get(10, TimeUnit.SECONDS);
            assertTrue(entered.await(5, TimeUnit.SECONDS));
            assertEquals(10, group.leader().status().applicationSequence());
            assertEquals(0, group.nodes.get(2).status().applicationSequence());
            armed.set(false); release.countDown();
            // Previously admitted transport requests retain their bounded deadlines before catch-up.
            V50LeaderPathTest.await(() -> group.nodes.get(2).status().appliedIndex() >= 2);
            group.leader().catchUp(group.manifest.members().get(2).nodeId()).get(15, TimeUnit.SECONDS);
            assertEquals(10, group.nodes.get(2).status().applicationSequence());
        } finally { release.countDown(); group.close(); }
    }

    @Test
    void duplicateReorderedAndStaleMessagesDoNotChangeCommittedState() throws Exception {
        var captured = new ConcurrentHashMap<String, Map<String, Object>>(); var armed = new AtomicBoolean();
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE, local -> (barrier, request, response) -> {
            if (local == 0 && armed.get() && barrier.equals("BEFORE_REQUEST_WRITE") && request.get("recipient").equals("node-2"))
                captured.put(request.get("type").toString(), request);
        })) {
            group.leader().activate().get(10, TimeUnit.SECONDS); armed.set(true);
            group.add(new Document(1, "shared")).get(10, TimeUnit.SECONDS);
            V50LeaderPathTest.await(() -> group.nodes.get(1).status().appliedIndex() == 2);
            var before = group.nodes.get(1).status(); int port = group.manifest.members().get(1).endpoint().port();
            for (String type : List.of("COMMIT_PROOF", "APPEND", "APPEND", "COMMIT_PROOF")) {
                assertNotEquals("REJECT", raw(port, captured.get(type)).get("type"));
                assertEquals(before, group.nodes.get(1).status());
            }
            var stale = new java.util.TreeMap<>(captured.get("APPEND")); stale.put("incarnationId", UUID.randomUUID().toString());
            assertEquals("STALE_EPOCH", ReplicaWire.object(raw(port, stale).get("payload")).get("reason"));
            var base = ReplicaEntry.decode(decodeRecord(Base64.getDecoder().decode(ReplicaWire.string(ReplicaWire.object(captured.get("APPEND").get("payload")), "entry")), ENTRY, BOUNDS.maxFrameBytes()));
            var next = new ReplicaEntry(group.manifest.digest(), base.epoch(), base.incarnation(), 3, "ADD", base.epoch(), 2,
                    frameDigest(base.encode(BOUNDS.maxFrameBytes())), group.applications.getFirst().documents("ADD", List.of(new Document(2, "later"))));
            String digest = frameDigest(next.encode(BOUNDS.maxFrameBytes()));
            var proof = new ReplicaProof(group.manifest.digest(), next.epoch(), next.incarnation(), 3, digest, next.previousDigest(),
                    List.of(ReplicaProof.acknowledgement(LEADER, next, digest), ReplicaProof.acknowledgement(group.manifest.members().get(1).nodeId(), next, digest)));
            var reordered = new java.util.TreeMap<>(captured.get("COMMIT_PROOF"));
            reordered.put("payload", Map.of("manifestDigest", group.manifest.digest(), "proof", Base64.getEncoder().encodeToString(proof.encode())));
            assertEquals("CONFLICTING_HISTORY", ReplicaWire.object(raw(port, reordered).get("payload")).get("reason"));
            assertEquals(before, group.nodes.get(1).status());
            group.add(new Document(2, "later")).get(10, TimeUnit.SECONDS);
            assertEquals(2, group.leader().status().applicationSequence());
        }
    }

    @ParameterizedTest
    @ValueSource(strings = {"truncated", "oversized", "checksum", "wrong-group", "wrong-recipient"})
    void malformedFramesNeverReachDurableAdmission(String corruption) throws Exception {
        try (var group = new Group(temporary, BOUNDS, ReplicaNode.Events.NONE)) {
            var peer = group.manifest.members().get(1).nodeId();
            var request = new java.util.TreeMap<>(ReplicaWire.message(group.manifest, LEADER, peer, 2, UUID.randomUUID(),
                    "ACTIVATE_EPOCH", Map.of("manifestDigest", group.manifest.digest(), "recovery", true), UUID.randomUUID(), 1));
            if (corruption.equals("wrong-group")) request.put("groupId", UUID.randomUUID().toString());
            if (corruption.equals("wrong-recipient")) request.put("recipient", "node-3");
            byte[] bytes = ReplicaWire.encode(request, BOUNDS.maxFrameBytes());
            if (corruption.equals("checksum")) bytes[16] ^= 1;
            if (corruption.equals("oversized")) { bytes = java.util.Arrays.copyOf(bytes, HEADER_BYTES); ByteBuffer.wrap(bytes).putInt(12, Integer.MAX_VALUE); }
            if (corruption.equals("truncated")) bytes = java.util.Arrays.copyOf(bytes, bytes.length - 1);
            var before = group.nodes.get(1).status();
            try (var socket = new Socket("127.0.0.1", group.manifest.members().get(1).endpoint().port())) {
                socket.setSoTimeout(4000); socket.getOutputStream().write(bytes); socket.shutdownOutput();
                assertEquals(-1, socket.getInputStream().read());
            }
            assertEquals(before, group.nodes.get(1).status());
        }
    }

    static ReplicaEntry appendEntry(Map<String, Object> request) throws IOException {
        return ReplicaEntry.decode(decodeRecord(Base64.getDecoder().decode(
                ReplicaWire.string(ReplicaWire.object(request.get("payload")), "entry")), ENTRY, BOUNDS.maxFrameBytes()));
    }

    static Map<String, Object> raw(int port, Map<String, Object> request) throws IOException {
        try (var socket = new Socket("127.0.0.1", port)) {
            socket.setSoTimeout(5000); socket.getOutputStream().write(ReplicaWire.encode(request, BOUNDS.maxFrameBytes()));
            byte[] header = socket.getInputStream().readNBytes(HEADER_BYTES);
            int length = ReplicaWire.bodyLength(header, BOUNDS.maxFrameBytes());
            byte[] bytes = java.util.Arrays.copyOf(header, HEADER_BYTES + length);
            byte[] body = socket.getInputStream().readNBytes(length); assertEquals(length, body.length);
            System.arraycopy(body, 0, bytes, HEADER_BYTES, length); return ReplicaWire.decode(bytes, BOUNDS.maxFrameBytes());
        }
    }
}
