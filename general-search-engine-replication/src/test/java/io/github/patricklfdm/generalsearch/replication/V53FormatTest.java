package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.MembershipFormat.*;
import static org.junit.jupiter.api.Assertions.*;
import io.github.patricklfdm.generalsearch.admission.AdmissionJson;
import java.io.*;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.Test;

class V53FormatTest {
    static Map<String, Object> fixtures() throws Exception {
        try (var in = V53FormatTest.class.getResourceAsStream("/replication/v53/byte-fixtures.json")) {
            if (in == null) throw new IllegalStateException("missing independent fixtures");
            return object(AdmissionJson.parse(new String(in.readAllBytes(), StandardCharsets.UTF_8)));
        }
    }
    static Map<String, Object> sample(String family, String name) throws Exception {
        return list(fixtures().get("fixtures")).stream().map(MembershipFormat::object)
                .filter(v -> v.get("family").equals(family) && v.get("name").equals(name)).findFirst().orElseThrow();
    }
    static byte[] bytes(Map<String, Object> sample) { return HexFormat.of().parseHex((String) sample.get("hex")); }
    static byte[] frame(byte[] original, String body) {
        byte[] raw = body.getBytes(StandardCharsets.US_ASCII);
        byte[] prefix = Arrays.copyOf(original, 16); ByteBuffer.wrap(prefix).putInt(12, raw.length);
        return ByteBuffer.allocate(HEADER + raw.length).put(prefix).put(sha(prefix, raw)).put(raw).array();
    }
    @Test void everyKindMatchesIndependentGoldenBytesAndDefensiveDecodedValues() throws Exception {
        var seen = new HashSet<String>();
        for (Object item : list(fixtures().get("fixtures"))) {
            var row = object(item); String family = (String) row.get("family"), name = (String) row.get("name");
            byte[] expected = bytes(row), before = expected.clone();
            assertTrue(seen.add(family+":"+name));
            assertArrayEquals(expected, encode(family, name, object(row.get("value"))), family+":"+name);
            var decoded = decode(expected, family, name);
            assertEquals(row.get("sha256"), decoded.digest());
            assertArrayEquals(expected, encode(family, name, decoded.value()));
            assertThrows(UnsupportedOperationException.class, () -> decoded.value().clear());
            byte[] exposed = decoded.bytes(); exposed[0] ^= 1;
            assertArrayEquals(expected, decoded.bytes()); assertArrayEquals(before, expected);
            assertEquals(decoded.value(), read(new ByteArrayInputStream(expected), family, name).value());
            if (name.equals("ROOT") && family.equals("records")) {
                assertEquals(HexFormat.of().formatHex(expected, 16, 48), decoded.rootDigest());
                assertNotEquals(decoded.digest(), decoded.rootDigest());
            } else assertThrows(IllegalArgumentException.class, decoded::rootDigest);
        }
        assertEquals(45, seen.size());
    }
    @Test void commandAndReadTokenEncodingRemainExact() throws Exception {
        for (Object item : list(fixtures().get("commandPayloads"))) {
            var row = object(item); String name = (String) row.get("name");
            byte[] expected = bytes(row);
            assertArrayEquals(expected, command(name, row.get("value")), name);
            assertArrayEquals(expected, command(name, command(name, expected)));
        }
        byte[] token = bytes(object(fixtures().get("unchangedReadTokenV1")));
        assertArrayEquals(token, ReplicaReadToken.decode(token).encode());
        byte[] application = new byte[] {1, 2, 3};
        byte[] encoded = command("DATA", (Object) application); encoded[0] = 7;
        assertArrayEquals(new byte[] {1, 2, 3}, application);
        assertThrows(IllegalArgumentException.class, () -> command("BARRIER", new byte[] {0}));
        assertThrows(IllegalArgumentException.class, () -> command("UNKNOWN", Map.of()));
    }
    @Test void malformedAndOlderHeadersFailBeforeReadingABody() throws Exception {
        byte[] original = bytes(sample("records", "ROOT"));
        for (int[] alteration : new int[][] {{4,0}, {6,1}, {6,2}, {6,4}, {8,100}, {10,1}, {12,0}, {12,Integer.MAX_VALUE}, {12,-1}}) {
            byte[] prefix = Arrays.copyOf(original, HEADER);
            if (alteration[0] == 12) ByteBuffer.wrap(prefix).putInt(12, alteration[1]);
            else ByteBuffer.wrap(prefix).putShort(alteration[0], (short) alteration[1]);
            var input = new ByteArrayInputStream(prefix) {
                @Override public byte[] readNBytes(int size) { assertEquals(48, size); return prefix; }
                @Override public synchronized int read(byte[] b, int off, int len) { fail("unvalidated payload read"); return -1; }
            };
            assertThrows(IllegalArgumentException.class, () -> read(input, "records", "ROOT"));
        }
        assertArrayEquals(original, bytes(sample("records", "ROOT")));
        assertThrows(EOFException.class, () -> read(new ByteArrayInputStream(Arrays.copyOf(original, HEADER)), "records", "ROOT"));
        assertThrows(IllegalArgumentException.class, () -> decode(Arrays.copyOf(original, original.length+1), "records", "ROOT"));
        byte[] corrupt = original.clone(); corrupt[16] ^= 1;
        assertThrows(IllegalArgumentException.class, () -> decode(corrupt, "records", "ROOT"));
    }
    @Test void canonicalDuplicateUnknownFloatAndShapeViolationsReject() throws Exception {
        byte[] original = bytes(sample("records", "ALLOCATOR"));
        String body = new String(original, HEADER, original.length-HEADER, StandardCharsets.US_ASCII);
        for (String bad : List.of(body.replace("\"counter\":0", "\"counter\":0,\"counter\":0"),
                body.replace("\"counter\":0", "\"counter\":0,\"other\":0"), body.replace("\"counter\":0", "\"counter\":0.0"),
                body.replace("\"counter\":0", "\"counter\":true"), body.replace("\"counter\":0", "\"counter\":-1"),
                " "+body, body.replace("node-1", "NODE-1"), body.replace("\"counter\":0", "\"counter\":00")))
            assertThrows(RuntimeException.class, () -> decode(frame(original, bad), "records", "ALLOCATOR"), bad);
        for (Object value : List.of(1.0, true, "1", -1L))
            assertThrows(IllegalArgumentException.class, () -> checkType(value, "positive"));
        assertThrows(IllegalArgumentException.class, () -> checkType("AQ==\n", "blob"));
        for (String relative : List.of("/tmp/a", "../a", "a/../b", "a//b", "a/", "a\\b"))
            assertThrows(IllegalArgumentException.class, () -> checkType(relative, "relative"));
    }
    @Test void parserCountsObjectKeysAndCapsNestingBeforeRecursiveDecoding() {
        byte[] nested = ("[".repeat(17)+"0"+"]".repeat(17)).getBytes(StandardCharsets.US_ASCII);
        assertThrows(IllegalArgumentException.class, () -> parserBudget(nested));
        var large = new StringBuilder("{");
        for (int i=0; i<32768; i++) { if (i>0) large.append(','); large.append('"').append('k').append(i).append("\":0"); }
        large.append('}');
        assertThrows(IllegalArgumentException.class, () -> parserBudget(large.toString().getBytes(StandardCharsets.US_ASCII)));
        assertDoesNotThrow(() -> parserBudget(("[".repeat(16)+"0"+"]".repeat(16)).getBytes(StandardCharsets.US_ASCII)));
        assertThrows(IllegalArgumentException.class, () -> parserBudget(new byte[] {'"',(byte) 0xff,'"'}));
    }
}
