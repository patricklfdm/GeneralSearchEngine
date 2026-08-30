package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.FuzzyVocabularyAccess;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;

/** V3.1 feature-lane trie traversal across scale, Unicode, and hit density. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class V31FuzzyDictionaryBenchmark {
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Analyzer IDENTITY_ANALYZER = text ->
            text == null || text.isEmpty()
                    ? List.of()
                    : List.of(new Token(text));
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, IDENTITY_ANALYZER);

    @Param({"100000", "1000000"})
    public int vocabularySize;

    @Param({
            "short-exact", "long-near", "unicode-near",
            "sparse-miss", "dense-hit"
    })
    public String scenario;

    private TextIndexSnapshot<Document> index;
    private String query;
    private int maxEdits;

    @Setup(Level.Trial)
    public void setUp() {
        IndexBuilder<Document> builder = IndexDefinition.text(BODY_TEXT)
                .createEmpty()
                .toBuilder();
        for (int documentId = 0; documentId < vocabularySize; documentId++) {
            builder.add(documentId, new Document(term(documentId)));
        }
        index = textIndex(builder.build());
        query = queryForScenario();
        int queryLength = query.codePointCount(0, query.length());
        maxEdits = queryLength <= 2 ? 0 : queryLength <= 5 ? 1 : 2;
        verifyAgainstFullScan();
    }

    @Benchmark
    public long traverse() {
        long[] checksum = {0L};
        FuzzyVocabularyAccess.forEachWithinEditDistance(
                index,
                query,
                maxEdits,
                (term, distance) -> checksum[0] = 31L * checksum[0]
                        + term.hashCode() + distance
        );
        return checksum[0];
    }

    private void verifyAgainstFullScan() {
        Map<String, Integer> expected = new HashMap<>();
        int[] queryPoints = query.codePoints().toArray();
        FuzzyVocabularyAccess.forEachTerm(index, candidate -> {
            int[] candidatePoints = candidate.codePoints().toArray();
            if (Math.abs(candidatePoints.length - queryPoints.length) <= maxEdits) {
                int distance = fullOsaDistance(candidatePoints, queryPoints);
                if (distance <= maxEdits) {
                    expected.put(candidate, distance);
                }
            }
        });
        Map<String, Integer> actual = new HashMap<>();
        FuzzyVocabularyAccess.forEachWithinEditDistance(
                index,
                query,
                maxEdits,
                (term, distance) -> {
                    if (actual.put(term, distance) != null) {
                        throw new IllegalStateException(
                                "duplicate fuzzy expansion: " + term);
                    }
                }
        );
        if (!expected.equals(actual)) {
            throw new IllegalStateException(
                    "trie traversal differs from full-scan OSA oracle");
        }
        boolean shouldMatch = !scenario.equals("sparse-miss");
        if (actual.isEmpty() == shouldMatch) {
            throw new IllegalStateException(
                    shouldMatch ? "expected fuzzy expansions" : "expected no expansion");
        }
    }

    private String term(int value) {
        if (scenario.equals("dense-hit") && value <= 625) {
            if (value == 0) {
                return "aaaaaaaa";
            }
            int pair = value - 1;
            int first = 'b' + pair / 25;
            int second = 'b' + pair % 25;
            return new String(new int[]{first, second, 'a', 'a', 'a', 'a', 'a', 'a'},
                    0, 8);
        }
        String suffix = Integer.toString(1_000_000 + value);
        return switch (scenario) {
            case "short-exact" -> "s" + suffix;
            case "long-near" -> "intercontinentaldestination" + suffix;
            case "unicode-near" -> "旅行\uD801\uDC00目的地" + suffix;
            case "sparse-miss" -> "destination" + suffix;
            case "dense-hit" -> "dense-destination" + suffix;
            default -> throw new IllegalArgumentException(
                    "unknown fuzzy scenario: " + scenario);
        };
    }

    private String queryForScenario() {
        return switch (scenario) {
            case "short-exact" -> term(0);
            case "long-near" -> "xntercontinentaldestination1000000";
            case "unicode-near" -> "旅行\uD801\uDC00目的天1000000";
            case "sparse-miss" -> "zzzzzzzzzzzzzzzzzz";
            case "dense-hit" -> "aaaaaaaa";
            default -> throw new IllegalArgumentException(
                    "unknown fuzzy scenario: " + scenario);
        };
    }

    private static int fullOsaDistance(int[] left, int[] right) {
        int[][] matrix = new int[left.length + 1][right.length + 1];
        for (int row = 0; row <= left.length; row++) {
            matrix[row][0] = row;
        }
        for (int column = 0; column <= right.length; column++) {
            matrix[0][column] = column;
        }
        for (int row = 1; row <= left.length; row++) {
            for (int column = 1; column <= right.length; column++) {
                int best = Math.min(
                        matrix[row - 1][column] + 1,
                        Math.min(
                                matrix[row][column - 1] + 1,
                                matrix[row - 1][column - 1]
                                        + (left[row - 1] == right[column - 1] ? 0 : 1)
                        )
                );
                if (row > 1
                        && column > 1
                        && left[row - 1] == right[column - 2]
                        && left[row - 2] == right[column - 1]) {
                    best = Math.min(best, matrix[row - 2][column - 2] + 1);
                }
                matrix[row][column] = best;
            }
        }
        return matrix[left.length][right.length];
    }

    @SuppressWarnings("unchecked")
    private static TextIndexSnapshot<Document> textIndex(Object value) {
        return (TextIndexSnapshot<Document>) value;
    }

    private record Document(String body) {
    }
}
