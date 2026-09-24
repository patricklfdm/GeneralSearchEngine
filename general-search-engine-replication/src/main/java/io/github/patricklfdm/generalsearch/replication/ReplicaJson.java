package io.github.patricklfdm.generalsearch.replication;

import static io.github.patricklfdm.generalsearch.replication.ReplicaFormat.require;
import static io.github.patricklfdm.generalsearch.replication.ReplicationException.Reason.*;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** The Phase 1 canonical ASCII JSON subset; bounded before encoding/recursive descent. */
final class ReplicaJson {
    private static final char[] HEX = "0123456789abcdef".toCharArray();
    private ReplicaJson() { }

    private static boolean letter(char c) { return c >= 'A' && c <= 'Z' || c >= 'a' && c <= 'z'; }
    static boolean key(String value) {
        if (value.isEmpty() || !letter(value.charAt(0))) return false;
        for (int i = 1; i < value.length(); i++) {
            char c = value.charAt(i);
            if (!letter(c) && !(c >= '0' && c <= '9') && c != '_') return false;
        }
        return true;
    }

    static byte[] encode(Object value, int maximum) {
        var output = new StringBuilder();
        append(value, output, maximum, 0, new int[]{100_000});
        return output.toString().getBytes(StandardCharsets.US_ASCII);
    }

    static Object decode(byte[] bytes, int maximum) {
        require(bytes.length <= maximum, CAPACITY_EXCEEDED, "JSON exceeds frame bound");
        for (byte value : bytes) require(value >= 0, PROTOCOL_MISMATCH, "JSON must be ASCII");
        var parser = new Parser(new String(bytes, StandardCharsets.US_ASCII));
        Object value = parser.value(0);
        require(parser.offset == parser.source.length(), PROTOCOL_MISMATCH, "trailing JSON bytes");
        require(Arrays.equals(bytes, encode(value, maximum)), PROTOCOL_MISMATCH, "noncanonical JSON");
        return value;
    }

    private static void append(Object value, StringBuilder out, int max, int depth, int[] remaining) {
        require(depth <= 16, CAPACITY_EXCEEDED, "JSON nesting exceeds bound");
        require(remaining[0]-- > 0, CAPACITY_EXCEEDED, "JSON value count exceeds bound");
        if (value == null || value instanceof Boolean || value instanceof Long || value instanceof Integer) {
            put(out, String.valueOf(value), max);
        } else if (value instanceof String string) {
            quote(string, out, max);
        } else if (value instanceof Map<?, ?> map) {
            require(map.size() <= remaining[0], CAPACITY_EXCEEDED, "JSON member count exceeds bound");
            var sorted = new TreeMap<String, Object>();
            for (var entry : map.entrySet()) {
                require(entry.getKey() instanceof String key && key(key),
                        PROTOCOL_MISMATCH, "invalid JSON object key");
                sorted.put((String) entry.getKey(), entry.getValue());
            }
            put(out, "{", max);
            boolean first = true;
            for (var entry : sorted.entrySet()) {
                if (!first) put(out, ",", max);
                first = false;
                quote(entry.getKey(), out, max);
                put(out, ":", max);
                append(entry.getValue(), out, max, depth + 1, remaining);
            }
            put(out, "}", max);
        } else if (value instanceof List<?> list) {
            require(list.size() <= remaining[0], CAPACITY_EXCEEDED, "JSON element count exceeds bound");
            put(out, "[", max);
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) put(out, ",", max);
                append(list.get(i), out, max, depth + 1, remaining);
            }
            put(out, "]", max);
        } else throw new ReplicationException(PROTOCOL_MISMATCH, "unsupported JSON value");
    }

    private static void quote(String value, StringBuilder out, int max) {
        put(out, "\"", max);
        int run = 0;
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c >= 32 && c < 127 && c != '\"' && c != '\\') continue;
            put(out, value, run, i, max);
            switch (c) {
                case '\"' -> put(out, "\\\"", max);
                case '\\' -> put(out, "\\\\", max);
                case '\b' -> put(out, "\\b", max);
                case '\f' -> put(out, "\\f", max);
                case '\n' -> put(out, "\\n", max);
                case '\r' -> put(out, "\\r", max);
                case '\t' -> put(out, "\\t", max);
                default -> {
                    require(6 <= max - out.length(), CAPACITY_EXCEEDED, "JSON exceeds frame bound");
                    out.append('\\').append('u').append(HEX[c >>> 12]).append(HEX[(c >>> 8) & 15])
                            .append(HEX[(c >>> 4) & 15]).append(HEX[c & 15]);
                }
            }
            run = i + 1;
        }
        put(out, value, run, value.length(), max);
        put(out, "\"", max);
    }

    private static void put(StringBuilder out, String value, int start, int end, int max) {
        require(end - start <= max - out.length(), CAPACITY_EXCEEDED, "JSON exceeds frame bound");
        out.append(value, start, end);
    }

    private static void put(StringBuilder out, String value, int max) {
        require(value.length() <= max - out.length(), CAPACITY_EXCEEDED, "JSON exceeds frame bound");
        out.append(value);
    }

    private static final class Parser {
        final String source;
        int offset, values;
        Parser(String source) { this.source = source; }
        char take() {
            require(offset < source.length(), PROTOCOL_MISMATCH, "incomplete JSON");
            return source.charAt(offset++);
        }
        void expect(char c) { require(take() == c, PROTOCOL_MISMATCH, "invalid JSON token"); }
        boolean consume(char c) {
            if (offset < source.length() && source.charAt(offset) == c) { offset++; return true; }
            return false;
        }
        Object value(int depth) {
            require(depth <= 16, CAPACITY_EXCEEDED, "JSON nesting exceeds bound");
            require(++values <= 100_000, CAPACITY_EXCEEDED, "JSON value count exceeds bound");
            char c = take();
            if (c == '"') return string();
            if (c == '{') {
                var map = new TreeMap<String, Object>();
                if (consume('}')) return map;
                do {
                    expect('"');
                    String key = string();
                    require(key(key) && !map.containsKey(key),
                            PROTOCOL_MISMATCH, "invalid/duplicate JSON key");
                    expect(':');
                    map.put(key, value(depth + 1));
                } while (consume(','));
                expect('}');
                return map;
            }
            if (c == '[') {
                var list = new ArrayList<Object>();
                if (consume(']')) return list;
                do { list.add(value(depth + 1)); } while (consume(','));
                expect(']');
                return list;
            }
            if (c == 't') { literal("rue"); return true; }
            if (c == 'f') { literal("alse"); return false; }
            if (c == 'n') { literal("ull"); return null; }
            int start = offset - 1;
            require(c == '-' || c >= '0' && c <= '9', PROTOCOL_MISMATCH, "invalid JSON number");
            while (offset < source.length() && source.charAt(offset) >= '0' && source.charAt(offset) <= '9') offset++;
            require(offset - start <= 20, PROTOCOL_MISMATCH, "JSON integer overflow");
            try { return Long.parseLong(source.substring(start, offset)); }
            catch (NumberFormatException error) { throw ReplicaFormat.failure(PROTOCOL_MISMATCH, "invalid JSON integer", error); }
        }
        void literal(String tail) { for (int i = 0; i < tail.length(); i++) expect(tail.charAt(i)); }
        String string() {
            var result = new StringBuilder();
            while (true) {
                char c = take();
                if (c == '"') return result.toString();
                require(c >= 32, PROTOCOL_MISMATCH, "unescaped JSON control");
                if (c == '\\') {
                    c = take();
                    c = switch (c) {
                        case '"', '\\', '/' -> c;
                        case 'b' -> '\b';
                        case 'f' -> '\f';
                        case 'n' -> '\n';
                        case 'r' -> '\r';
                        case 't' -> '\t';
                        case 'u' -> {
                            int code = 0;
                            for (int i = 0; i < 4; i++) {
                                int digit = Character.digit(take(), 16);
                                require(digit >= 0, PROTOCOL_MISMATCH, "invalid Unicode escape");
                                code = code * 16 + digit;
                            }
                            yield (char) code;
                        }
                        default -> throw new ReplicationException(PROTOCOL_MISMATCH, "invalid JSON escape");
                    };
                }
                result.append(c);
            }
        }
    }
}
