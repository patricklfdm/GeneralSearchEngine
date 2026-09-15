package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import static io.github.patricklfdm.generalsearch.replication.ReplicaLeaderTestSupport.*;

import java.net.InetAddress;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

class V50WireCodecTest {
    @Test
    void productionCodecMatchesAllIndependentPhase1GoldenFrames() throws Exception {
        String fixture = Files.readString(Path.of(getClass().getResource("/replication/v50-wire-fixtures.json").toURI()));
        var matcher = Pattern.compile("\"hex\"\\s*:\\s*\"([0-9a-f]+)\"").matcher(fixture);
        int count = 0;
        while (matcher.find()) {
            byte[] frame = HexFormat.of().parseHex(matcher.group(1));
            assertArrayEquals(frame, ReplicaWire.encode(ReplicaWire.decode(frame, BOUNDS.maxFrameBytes()), BOUNDS.maxFrameBytes()));
            count++;
        }
        assertEquals(16, count);
    }

    @Test
    void rejectsNoncanonicalMalformedAndOversizedFrames() throws Exception {
        var manifest = manifest(List.of(20001, 20002, 20003));
        var message = ReplicaWire.message(manifest, LEADER, manifest.members().get(1).nodeId(), 2,
                UUID.randomUUID(), "APPEND", Map.of("manifestDigest", manifest.digest()), UUID.randomUUID(), 1);
        byte[] original = ReplicaWire.encode(message, BOUNDS.maxFrameBytes());
        for (int offset : new int[] {0, 5, 7, 9, 11, 16, original.length - 1}) {
            byte[] changed = original.clone(); changed[offset] ^= 1;
            assertThrows(ReplicationException.class, () -> ReplicaWire.decode(changed, BOUNDS.maxFrameBytes()));
        }
        for (int length : new int[] {0, 47, original.length - 1, original.length + 1}) {
            byte[] changed = Arrays.copyOf(original, length);
            assertThrows(ReplicationException.class, () -> ReplicaWire.decode(changed, BOUNDS.maxFrameBytes()));
        }
        byte[] header = Arrays.copyOf(original, 48); ByteBuffer.wrap(header).putInt(12, Integer.MAX_VALUE);
        assertEquals(ReplicationException.Reason.CAPACITY_EXCEEDED,
                assertThrows(ReplicationException.class, () -> ReplicaWire.bodyLength(header, BOUNDS.maxFrameBytes())).reason());
        for (String invalid : List.of("{\"x\":1,\"x\":2}", "{\"x\": 1}", "{\"x\":01}", "{\"x\":-0}",
                "{\"x\":9223372036854775808}", "{\"x\":1.0}", "{\"x\":\"\\u0041\"}", "{\"x\":\"\\u00AF\"}",
                "[".repeat(18) + "0" + "]".repeat(18))) {
            assertThrows(ReplicationException.class, () -> ReplicaJson.decode(invalid.getBytes(StandardCharsets.US_ASCII), 4096), invalid);
        }
        var unicode = Map.of("value", "\b\t\n\f\r\"\\\u007f你好😀");
        byte[] encoded = ReplicaJson.encode(unicode, 4096);
        assertEquals(unicode, ReplicaJson.decode(encoded, 4096));
        String excessive = "[" + "0,".repeat(100_000) + "0]";
        assertEquals(ReplicationException.Reason.CAPACITY_EXCEEDED,
                assertThrows(ReplicationException.class, () -> ReplicaJson.decode(excessive.getBytes(StandardCharsets.US_ASCII), 1024 * 1024)).reason());
    }

    @Test
    void bindAdmissionRejectsWildcardPublicMulticastAndAcceptsPrivateIpv6() throws Exception {
        for (String address : List.of("0.0.0.0", "::", "8.8.8.8", "224.0.0.1", "2001:4860:4860::8888"))
            assertFalse(ReplicaTransport.privateAddress(InetAddress.getByName(address)));
        for (String address : List.of("127.0.0.1", "::1", "10.1.2.3", "172.16.0.1", "192.168.1.2", "fd00::1"))
            assertTrue(ReplicaTransport.privateAddress(InetAddress.getByName(address)));
    }

    @Test
    void peerResponsesMustEchoTraceEpochIncarnationAndVoter() throws Exception {
        var manifest = manifest(ports());
        var peer = manifest.members().get(1).nodeId();
        try (var server = new ReplicaTransport(manifest, peer, BOUNDS, request -> {
            var response = new java.util.TreeMap<>(request);
            response.put("sender", peer.value()); response.put("recipient", LEADER.value());
            response.put("traceId", UUID.randomUUID().toString());
            return response;
        }); var client = new ReplicaTransport(manifest, LEADER, BOUNDS, request -> request)) {
            var request = ReplicaWire.message(manifest, LEADER, peer, 2, UUID.randomUUID(), "AUTHORITY_STATUS_PROBE",
                    Map.of("manifestDigest", manifest.digest()), UUID.randomUUID(), 1);
            V50LeaderPathTest.rejected(ReplicationException.Reason.PROTOCOL_MISMATCH, client.exchange(peer, request));
        }
    }

    @Test
    void perPeerAdmissionRejectsWhileItsOnlySlotIsBusy() throws Exception {
        var manifest = manifest(ports());
        var peer = manifest.members().get(1).nodeId();
        var entered = new java.util.concurrent.CountDownLatch(1);
        var release = new java.util.concurrent.CountDownLatch(1);
        var bounds = new ReplicationBounds(8192, 1, 1, 1, 1, 2000, 10, 1024, 1048576, 1048576);
        try (var server = new ReplicaTransport(manifest, peer, bounds, request -> {
            entered.countDown();
            try { release.await(5, java.util.concurrent.TimeUnit.SECONDS); }
            catch (InterruptedException error) { Thread.currentThread().interrupt(); throw new RuntimeException(error); }
            var response = new java.util.TreeMap<>(request);
            response.put("sender", peer.value()); response.put("recipient", LEADER.value()); return response;
        }); var client = new ReplicaTransport(manifest, LEADER, bounds, request -> request)) {
            var request = ReplicaWire.message(manifest, LEADER, peer, 2, UUID.randomUUID(), "AUTHORITY_STATUS_PROBE",
                    Map.of("manifestDigest", manifest.digest()), UUID.randomUUID(), 1);
            var first = client.exchange(peer, request);
            assertTrue(entered.await(5, java.util.concurrent.TimeUnit.SECONDS));
            V50LeaderPathTest.rejected(ReplicationException.Reason.CAPACITY_EXCEEDED, client.exchange(peer, request));
            release.countDown(); first.get(5, java.util.concurrent.TimeUnit.SECONDS);
        } finally { release.countDown(); }
    }
}
