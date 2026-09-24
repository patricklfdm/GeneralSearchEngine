package io.github.patricklfdm.generalsearch.replication;

import static org.junit.jupiter.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.junit.jupiter.api.Test;

class V51CanonicalJsonTest {
    @Test void everyUtf16CodeUnitKeepsItsCanonicalBytes() {
        var input = new StringBuilder();
        var expected = new StringBuilder("\"");
        for (int i = 0; i <= Character.MAX_VALUE; i++) {
            char c = (char) i; input.append(c);
            expected.append(switch (c) {
                case '"' -> "\\\""; case '\\' -> "\\\\";
                case '\b' -> "\\b"; case '\f' -> "\\f"; case '\n' -> "\\n";
                case '\r' -> "\\r"; case '\t' -> "\\t";
                default -> c < 32 || c >= 127 ? String.format(Locale.ROOT, "\\u%04x", i) : String.valueOf(c);
            });
        }
        byte[] golden = expected.append('"').toString().getBytes(StandardCharsets.US_ASCII);
        assertArrayEquals(golden, ReplicaJson.encode(input.toString(), golden.length));
        assertEquals(input.toString(), ReplicaJson.decode(golden, golden.length));
        assertThrows(ReplicationException.class, () -> ReplicaJson.encode(input.toString(), golden.length - 1));
    }

    @Test void asciiRunsAndEveryEscapeKeepTheSameExactSizeCeiling() {
        for (String text : List.of("", "plain", "a".repeat(100_000), "\"", "\\", "\b", "\f", "\n", "\r", "\t", "\0", "\u007f", "中", "\ud83d\ude03")) {
            var value = Map.of("field", List.of("prefix" + text + "suffix", 1L));
            byte[] bytes = ReplicaJson.encode(value, 1 << 20);
            assertArrayEquals(bytes, ReplicaJson.encode(value, bytes.length));
            assertEquals(value, ReplicaJson.decode(bytes, bytes.length));
            assertThrows(ReplicationException.class, () -> ReplicaJson.encode(value, bytes.length - 1));
            assertThrows(ReplicationException.class, () -> ReplicaJson.decode(bytes, bytes.length - 1));
        }
    }

    @Test void keyValidationPreservesAsciiGrammarOnBothPaths() {
        for (String key : List.of("a", "Z9_", "key".repeat(100), "", "_a", "1a", "a-b", "a b", "é", "a\n")) {
            boolean accepted = key.matches("[A-Za-z][A-Za-z0-9_]*");
            byte[] raw = ("{" + new String(ReplicaJson.encode(key, 4096), StandardCharsets.US_ASCII) + ":1}").getBytes(StandardCharsets.US_ASCII);
            if (accepted) {
                assertArrayEquals(raw, ReplicaJson.encode(Map.of(key, 1L), 4096));
                assertEquals(Map.of(key, 1L), ReplicaJson.decode(raw, 4096));
            } else {
                assertThrows(ReplicationException.class, () -> ReplicaJson.encode(Map.of(key, 1L), 4096));
                assertThrows(ReplicationException.class, () -> ReplicaJson.decode(raw, 4096));
            }
        }
    }

    @Test void everyCodeUnitPreservesTheOriginalAsciiGrammars() {
        var key = java.util.regex.Pattern.compile("[A-Za-z][A-Za-z0-9_]*");
        var id = java.util.regex.Pattern.compile("[a-z0-9][a-z0-9._-]{0,127}");
        var hash = java.util.regex.Pattern.compile("[0-9a-f]{64}");
        for (int i = 0; i <= Character.MAX_VALUE; i++) {
            String unit = String.valueOf((char) i);
            for (String value : List.of(unit, "a" + unit)) {
                assertEquals(key.matcher(value).matches(), ReplicaJson.key(value));
                for (String type : List.of("node", "id")) {
                    if (id.matcher(value).matches()) AutomaticRecords.schema(type, value, 0);
                    else assertThrows(AutomaticReplicationException.class, () -> AutomaticRecords.schema(type, value, 0));
                }
            }
            String value = "f".repeat(63) + unit;
            if (hash.matcher(value).matches()) AutomaticRecords.schema("hash", value, 0);
            else assertThrows(AutomaticReplicationException.class, () -> AutomaticRecords.schema("hash", value, 0));
        }
    }

    @Test void scalarValidationKeepsLengthAndCharacterRestrictions() {
        for (String type : List.of("hash", "node", "id")) {
            String regex = type.equals("hash") ? "[0-9a-f]{64}" : "[a-z0-9][a-z0-9._-]{0," + (type.equals("node") ? 63 : 127) + "}";
            for (String value : List.of("", "a", "a-b_0.x", "A", "_a", "é", "a\n", "f".repeat(63), "f".repeat(64), "f".repeat(65), "f".repeat(128), "f".repeat(129))) {
                if (value.matches(regex)) assertDoesNotThrow(() -> AutomaticRecords.schema(type, value, 0));
                else assertThrows(AutomaticReplicationException.class, () -> AutomaticRecords.schema(type, value, 0));
            }
        }
    }
}
