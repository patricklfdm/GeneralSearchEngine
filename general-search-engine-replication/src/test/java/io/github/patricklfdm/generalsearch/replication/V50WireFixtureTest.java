package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

class V50WireFixtureTest {
    @Test
    void independentlyChecksPythonGoldenFramesWithJdkBinaryAndDigestPrimitives() throws Exception {
        try (var input = getClass().getResourceAsStream("/replication/v50-wire-fixtures.json")) {
            String fixture = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            var frames = Pattern.compile("\"hex\":\\s*\"([0-9a-f]+)\"").matcher(fixture);
            int count = 0;
            while (frames.find()) {
                byte[] frame = HexFormat.of().parseHex(frames.group(1));
                ByteBuffer header = ByteBuffer.wrap(frame);
                assertEquals(0x47535250, header.getInt());
                assertEquals(1, Short.toUnsignedInt(header.getShort()));
                assertEquals(0, Short.toUnsignedInt(header.getShort()));
                assertEquals(++count, Short.toUnsignedInt(header.getShort()));
                assertEquals(0, Short.toUnsignedInt(header.getShort()));
                assertEquals(frame.length - 48, header.getInt());
                assertTrue(frame.length <= ReplicationBounds.defaults().maxFrameBytes());
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                digest.update(frame, 0, 16);
                digest.update(frame, 48, frame.length - 48);
                assertArrayEquals(Arrays.copyOfRange(frame, 16, 48), digest.digest());
                String body = new String(frame, 48, frame.length - 48, StandardCharsets.US_ASCII);
                for (String field : new String[]{"protocol", "groupId", "configurationId",
                        "sender", "recipient", "epoch", "incarnationId", "traceId", "eventSequence"}) {
                    assertTrue(body.contains("\"" + field + "\":"), field);
                }
            }
            assertEquals(16, count);
        }
    }
}
