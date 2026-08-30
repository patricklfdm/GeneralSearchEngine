package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.FuzzyVocabularyAccess;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchExecutionAccess;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshotBuilder;
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

/** Measures persistent-trie fuzzy planning plus top-K execution. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MILLISECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class FuzzySearchBenchmark {
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Param({"10000", "100000"})
    public int vocabularySize;

    @Param({
            "exact",
            "substitution",
            "insertion",
            "deletion",
            "transposition",
            "two-edits",
            "no-match",
            "high-expansion"
    })
    public String scenario;

    private final CandidatePlanner<Document> planner = new CandidatePlanner<>();
    private SearchSnapshot<Document> snapshot;
    private SearchRequest<Document> fuzzy;
    private SearchRequest<Document> composedFuzzy;

    @Setup(Level.Trial)
    public void setUp() {
        SearchSnapshotBuilder<Document> builder = new SearchSnapshotBuilder<>(
                new SearchSnapshot<>(List.of(
                        IndexDefinition.text(TITLE_TEXT),
                        IndexDefinition.text(BODY_TEXT)
                ))
        );
        for (int docId = 0; docId < vocabularySize; docId++) {
            builder.add(docId, new Document(
                    docId,
                    docId % 3 == 0 ? "featured travel" : "standard travel",
                    vocabularyTerm(docId, scenario)
            ));
        }
        snapshot = builder.build();
        String queryText = queryText(scenario);
        verifyTrieExpansion(snapshot, queryText);
        fuzzy = SearchRequest.<Document>builder()
                .query(SearchQueries.fuzzy(BODY_TEXT, queryText))
                .limit(10)
                .build();
        composedFuzzy = SearchRequest.<Document>builder()
                .query(SearchQueries.<Document>bool()
                        .must(SearchQueries.fuzzy(
                                BODY_TEXT,
                                queryText
                        ))
                        .should(SearchQueries.text(
                                TITLE_TEXT,
                                "featured"
                        ).boost(1.5))
                        .build())
                .limit(10)
                .build();

        boolean expectMatch = !"no-match".equals(scenario);
        verify(
                SearchExecutionAccess.search(snapshot, fuzzy, planner).hits(),
                expectMatch
        );
        verify(SearchExecutionAccess.search(
                snapshot,
                composedFuzzy,
                planner
        ).hits(), expectMatch);
    }

    @Benchmark
    public double fuzzyPlanAndTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                fuzzy,
                planner
        ).hits());
    }

    @Benchmark
    public double composedFuzzyPlanAndTop10() {
        return firstScore(SearchExecutionAccess.search(
                snapshot,
                composedFuzzy,
                planner
        ).hits());
    }

    private static String vocabularyTerm(int value, String scenario) {
        if ("high-expansion".equals(scenario)) {
            if (value == 0) {
                return "aaaaaaaa";
            }
            if (value <= 625) {
                int pair = value - 1;
                char first = (char) ('b' + pair / 25);
                char second = (char) ('b' + pair % 25);
                return new String(new char[]{
                        first, second, 'a', 'a', 'a', 'a', 'a', 'a'
                });
            }
        }
        return String.format(Locale.ROOT, "destination%05d", value);
    }

    private static String queryText(String scenario) {
        return switch (scenario) {
            case "exact" -> "destination00000";
            case "substitution" -> "xestination00000";
            case "insertion" -> "xdestination00000";
            case "deletion" -> "estination00000";
            case "transposition" -> "edstination00000";
            case "two-edits" -> "xxstination00000";
            case "no-match" -> "zzzzzzzzzzzzzzzz";
            case "high-expansion" -> "aaaaaaaa";
            default -> throw new IllegalArgumentException(
                    "unknown fuzzy scenario: " + scenario);
        };
    }

    private static void verify(
            List<SearchHit<Document>> hits,
            boolean expectMatch
    ) {
        if (hits.isEmpty() == expectMatch) {
            throw new IllegalStateException(
                    expectMatch
                            ? "expected benchmark hits"
                            : "expected no benchmark hits");
        }
        double previous = Double.POSITIVE_INFINITY;
        for (SearchHit<Document> hit : hits) {
            if (hit.score() > previous) {
                throw new IllegalStateException("scores are not descending");
            }
            previous = hit.score();
        }
    }

    private static double firstScore(List<SearchHit<Document>> hits) {
        return hits.isEmpty() ? 0.0 : hits.getFirst().score();
    }

    private static void verifyTrieExpansion(
            SearchSnapshot<Document> snapshot,
            String queryTerm
    ) {
        TextIndexSnapshot<?> textIndex = snapshot.indexes().indexes().stream()
                .filter(index -> index instanceof TextIndexSnapshot<?>)
                .map(index -> (TextIndexSnapshot<?>) index)
                .filter(index -> index.textField() == BODY_TEXT)
                .findFirst()
                .orElseThrow();
        int queryLength = queryTerm.codePointCount(0, queryTerm.length());
        int maxEdits = queryLength <= 2 ? 0 : queryLength <= 5 ? 1 : 2;
        int[] queryPoints = queryTerm.codePoints().toArray();
        int[] candidatePoints = new int[queryLength + maxEdits];
        int[] twoRowsBack = new int[queryLength + 1];
        int[] previous = new int[queryLength + 1];
        int[] current = new int[queryLength + 1];
        Map<String, Integer> expected = new HashMap<>();
        FuzzyVocabularyAccess.forEachTerm(textIndex, candidate -> {
            int candidateLength = candidate.codePointCount(0, candidate.length());
            if (Math.abs(candidateLength - queryLength) > maxEdits) {
                return;
            }
            copyCodePoints(candidate, candidatePoints);
            int distance = fullOsaDistance(
                    candidatePoints,
                    candidateLength,
                    queryPoints,
                    twoRowsBack,
                    previous,
                    current
            );
            if (distance <= maxEdits) {
                expected.put(candidate, distance);
            }
        });

        Map<String, Integer> actual = new HashMap<>();
        FuzzyVocabularyAccess.forEachWithinEditDistance(
                textIndex,
                queryTerm,
                maxEdits,
                (term, distance) -> {
                    if (actual.put(term, distance) != null) {
                        throw new IllegalStateException(
                                "duplicate trie expansion: " + term);
                    }
                }
        );
        if (!expected.equals(actual)) {
            throw new IllegalStateException(
                    "trie expansion differs from the full-scan OSA oracle");
        }
    }

    private static int fullOsaDistance(
            int[] left,
            int leftLength,
            int[] right,
            int[] twoRowsBack,
            int[] previous,
            int[] current
    ) {
        for (int column = 0; column <= right.length; column++) {
            previous[column] = column;
        }
        for (int row = 1; row <= leftLength; row++) {
            current[0] = row;
            for (int column = 1; column <= right.length; column++) {
                int best = Math.min(
                        previous[column] + 1,
                        Math.min(
                                current[column - 1] + 1,
                                previous[column - 1]
                                        + (left[row - 1] == right[column - 1]
                                                ? 0 : 1)
                        )
                );
                if (row > 1
                        && column > 1
                        && left[row - 1] == right[column - 2]
                        && left[row - 2] == right[column - 1]) {
                    best = Math.min(best, twoRowsBack[column - 2] + 1);
                }
                current[column] = best;
            }
            int[] reusable = twoRowsBack;
            twoRowsBack = previous;
            previous = current;
            current = reusable;
        }
        return previous[right.length];
    }

    private static void copyCodePoints(String value, int[] destination) {
        Arrays.fill(destination, 0);
        int sourceOffset = 0;
        int destinationOffset = 0;
        while (sourceOffset < value.length()) {
            int codePoint = value.codePointAt(sourceOffset);
            destination[destinationOffset++] = codePoint;
            sourceOffset += Character.charCount(codePoint);
        }
    }

    private record Document(int id, String title, String body) {
    }
}
