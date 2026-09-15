package io.github.patricklfdm.generalsearch.admission;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** Test-only independent JSON reader/canonical writer; no production codec imports. */
public final class AdmissionJson {
    private final String text;
    private int offset;
    private AdmissionJson(String text) { this.text = text; }

    public static Object parse(String text) {
        var parser = new AdmissionJson(text);
        Object value = parser.value(0);
        parser.space();
        require(parser.offset == text.length(), "JSON trailing bytes");
        return value;
    }

    static String canonical(Object value) {
        if (value == null) return "null";
        if (value instanceof String s) {
            var result = new StringBuilder("\"");
            for (char c : s.toCharArray()) {
                switch (c) {
                    case '"' -> result.append("\\\"");
                    case '\\' -> result.append("\\\\");
                    case '\b' -> result.append("\\b");
                    case '\f' -> result.append("\\f");
                    case '\n' -> result.append("\\n");
                    case '\r' -> result.append("\\r");
                    case '\t' -> result.append("\\t");
                    default -> {
                        if (c < 32 || c >= 127) result.append(String.format("\\u%04x", (int) c));
                        else result.append(c);
                    }
                }
            }
            return result.append('"').toString();
        }
        if (value instanceof Boolean || value instanceof Long || value instanceof Integer) return value.toString();
        if (value instanceof List<?> list) return "[" + String.join(",", list.stream().map(AdmissionJson::canonical).toList()) + "]";
        if (value instanceof Map<?, ?> map) {
            var sorted = new TreeMap<String, Object>();
            map.forEach((k, v) -> sorted.put((String) k, v));
            return "{" + String.join(",", sorted.entrySet().stream().map(e -> canonical(e.getKey()) + ":" + canonical(e.getValue())).toList()) + "}";
        }
        throw new IllegalArgumentException("JSON type");
    }

    private Object value(int depth) {
        require(depth <= 16, "JSON depth");
        space();
        char c = peek();
        if (c == '"') return string();
        if (c == '{') {
            offset++;
            var map = new TreeMap<String, Object>();
            space();
            if (peek() == '}') { offset++; return map; }
            do {
                space(); String key = string(); space(); take(':');
                require(!map.containsKey(key), "duplicate JSON key");
                map.put(key, value(depth + 1)); space();
                c = next(); require(c == ',' || c == '}', "JSON object separator");
            } while (c == ',');
            return map;
        }
        if (c == '[') {
            offset++;
            var list = new ArrayList<Object>();
            space();
            if (peek() == ']') { offset++; return list; }
            do {
                list.add(value(depth + 1)); space();
                c = next(); require(c == ',' || c == ']', "JSON array separator");
            } while (c == ',');
            return list;
        }
        for (String token : List.of("true", "false", "null")) {
            if (text.startsWith(token, offset)) {
                offset += token.length();
                return token.equals("null") ? null : Boolean.valueOf(token);
            }
        }
        int start = offset;
        if (peek() == '-') offset++;
        while (offset < text.length() && text.charAt(offset) >= '0' && text.charAt(offset) <= '9') offset++;
        String number = text.substring(start, offset);
        require(number.matches("-?(0|[1-9][0-9]*)"), "JSON integer");
        return Long.valueOf(number);
    }

    private String string() {
        take('"');
        var value = new StringBuilder();
        for (char c = next(); c != '"'; c = next()) {
            require(c >= 32, "JSON control character");
            if (c == '\\') {
                c = next();
                switch (c) {
                    case '"', '\\', '/' -> value.append(c);
                    case 'b' -> value.append('\b');
                    case 'f' -> value.append('\f');
                    case 'n' -> value.append('\n');
                    case 'r' -> value.append('\r');
                    case 't' -> value.append('\t');
                    case 'u' -> {
                        int point = 0;
                        for (int i = 0; i < 4; i++) {
                            int digit = Character.digit(next(), 16);
                            require(digit >= 0, "JSON escape"); point = point * 16 + digit;
                        }
                        value.append((char) point);
                    }
                    default -> throw new IllegalArgumentException("JSON escape");
                }
            } else value.append(c);
        }
        return value.toString();
    }
    private void space() { while (offset < text.length() && " \n\r\t".indexOf(text.charAt(offset)) >= 0) offset++; }
    private char peek() { require(offset < text.length(), "JSON truncated"); return text.charAt(offset); }
    private char next() { char c = peek(); offset++; return c; }
    private void take(char c) { require(next() == c, "JSON token"); }
    static void require(boolean value, String reason) { if (!value) throw new IllegalArgumentException(reason); }
}
