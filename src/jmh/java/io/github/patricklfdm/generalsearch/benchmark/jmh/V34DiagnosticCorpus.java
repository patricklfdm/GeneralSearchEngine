package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzer;

/** Deterministic, bounded corpus generator shared only by V3.4 diagnostics. */
final class V34DiagnosticCorpus {
    static final int MAX_DOCUMENTS = 1_000_000;
    static final int MAX_TOKENS_PER_FIELD = 16_384;

    private V34DiagnosticCorpus() {
    }

    static List<Document> generate(Config config) {
        List<Document> documents = new ArrayList<>(config.documentCount());
        for (int id = 0; id < config.documentCount(); id++) {
            boolean eligible = (id & 1) == 0;
            String control = eligible ? "anchor exact" : "unrelated exact";
            String primary = control + tail(config, id, eligible, false);
            String secondary = (eligible ? "secondary anchor" : "secondary decoy")
                    + tail(config, id, eligible, true);
            documents.add(new Document(
                    id,
                    primary,
                    secondary,
                    eligible ? "eligible" : "other",
                    "group-" + Math.floorMod(id, 7)
            ));
        }
        return List.copyOf(documents);
    }

    static Analyzer analyzer(Axis axis) {
        return axis == Axis.POSITION_HEAVY
                ? GapOffsetAnalyzer.INSTANCE
                : Analyzer.simple();
    }

    static String digest(List<Document> documents) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
        for (Document document : documents) {
            update(digest, Integer.toString(document.id()));
            update(digest, document.primary());
            update(digest, document.secondary());
            update(digest, document.category());
            update(digest, document.dynamicCategory());
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    static List<Integer> expectedEligibleIds(int documentCount) {
        List<Integer> ids = new ArrayList<>((documentCount + 1) / 2);
        for (int id = 0; id < documentCount; id += 2) {
            ids.add(id);
        }
        return List.copyOf(ids);
    }

    private static String tail(
            Config config,
            int documentId,
            boolean eligible,
            boolean secondary
    ) {
        StringBuilder value = new StringBuilder(config.tokensPerField() * 12);
        int tokenCount = config.tokensPerField();
        long mixedSeed = mix(config.seed(), documentId, secondary ? 1 : 0);
        for (int token = 0; token < tokenCount; token++) {
            value.append(' ');
            switch (config.axis()) {
                case LONG_TEXT -> value.append("longform").append(token % 31);
                case HIGH_FREQUENCY -> value.append("frequency");
                case LARGE_VOCABULARY -> value.append('v').append(Long.toUnsignedString(
                        mix(mixedSeed, token, documentId), 36));
                case SPARSE_VOCABULARY -> value.append('s').append(
                        Math.floorMod(token + config.seed(), 3L));
                case ZIPF_HEAVY -> value.append('z').append(zipfBucket(token));
                case MULTIPLE_FIELDS -> value.append(secondary ? "secondary" : "primary")
                        .append(token % 17);
                case UNICODE_HEAVY -> value.append(switch (token % 5) {
                    case 0 -> "café";
                    case 1 -> "東京";
                    case 2 -> "e\u0301lan";
                    case 3 -> "δοκιμή";
                    default -> "😀search";
                });
                case REPEATED_TERMS -> value.append(
                        eligible ? "anchor" : "decoy");
                case POSITION_HEAVY -> value.append(token % 2 == 0
                        ? "gap"
                        : "position");
            }
        }
        return value.toString();
    }

    private static int zipfBucket(int token) {
        int value = token + 1;
        return Math.min(63, Integer.numberOfTrailingZeros(
                Integer.highestOneBit(value) == value ? value : value & -value));
    }

    private static long mix(long seed, long left, long right) {
        long value = seed ^ (left * 0x9E3779B97F4A7C15L)
                ^ (right * 0xC2B2AE3D27D4EB4FL);
        value ^= value >>> 33;
        value *= 0xFF51AFD7ED558CCDL;
        value ^= value >>> 33;
        value *= 0xC4CEB9FE1A85EC53L;
        return value ^ (value >>> 33);
    }

    private static void update(MessageDigest digest, String value) {
        digest.update(value.getBytes(StandardCharsets.UTF_8));
        digest.update((byte) 0);
    }

    enum Axis {
        LONG_TEXT("long-text"),
        HIGH_FREQUENCY("high-frequency"),
        LARGE_VOCABULARY("large-vocabulary"),
        SPARSE_VOCABULARY("sparse-vocabulary"),
        ZIPF_HEAVY("zipf-heavy"),
        MULTIPLE_FIELDS("multiple-fields"),
        UNICODE_HEAVY("unicode-heavy"),
        REPEATED_TERMS("repeated-terms"),
        POSITION_HEAVY("position-heavy");

        private final String id;

        Axis(String id) {
            this.id = id;
        }

        String id() {
            return id;
        }

        static Axis parse(String value) {
            for (Axis axis : values()) {
                if (axis.id.equals(value)) {
                    return axis;
                }
            }
            throw new IllegalArgumentException("unknown corpus axis: " + value);
        }
    }

    record Config(int documentCount, int tokensPerField, long seed, Axis axis) {
        Config {
            if (documentCount <= 0 || documentCount > MAX_DOCUMENTS) {
                throw new IllegalArgumentException(
                        "documentCount must be in [1, " + MAX_DOCUMENTS + "]");
            }
            if (tokensPerField < 2
                    || tokensPerField > MAX_TOKENS_PER_FIELD) {
                throw new IllegalArgumentException(
                        "tokensPerField must be in [2, "
                                + MAX_TOKENS_PER_FIELD + "]");
            }
            if (axis == null) {
                throw new NullPointerException("axis");
            }
        }
    }

    record Document(
            int id,
            String primary,
            String secondary,
            String category,
            String dynamicCategory
    ) {
    }

    private enum GapOffsetAnalyzer implements OffsetAnalyzer {
        INSTANCE;

        @Override
        public List<OffsetAnalyzedToken> analyzeWithOffsets(String text) {
            List<OffsetAnalyzedToken> tokens = new ArrayList<>();
            int cursor = 0;
            while (cursor < text.length()) {
                while (cursor < text.length()
                        && Character.isWhitespace(text.charAt(cursor))) {
                    cursor++;
                }
                if (cursor == text.length()) {
                    break;
                }
                int start = cursor;
                while (cursor < text.length()
                        && !Character.isWhitespace(text.charAt(cursor))) {
                    cursor++;
                }
                String term = text.substring(start, cursor)
                        .toLowerCase(Locale.ROOT);
                int increment = term.equals("gap") ? 64 : 1;
                tokens.add(new OffsetAnalyzedToken(
                        term,
                        increment,
                        start,
                        cursor
                ));
            }
            return List.copyOf(tokens);
        }
    }
}
