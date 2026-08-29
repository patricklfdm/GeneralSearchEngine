package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class RankedCompositionDifferentialTest {
    private static final Field<Document, String> TITLE =
            Field.of("title", String.class, Document::title);
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final Field<Document, String> CATEGORY =
            Field.of("category", String.class, Document::category);
    private static final TextField<Document> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Document> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());
    private static final String[] TERMS = {
            "java", "search", "engine", "snapshot", "unknown", "---"
    };
    private static final double[] BOOSTS = {0.25, 0.5, 2.0, 3.0};

    @Test
    void matchesTrustedRecursiveEvaluatorAcrossRandomTrees() {
        Random random = new Random(40_004);
        List<Document> documents = randomDocuments(random, 30);
        SearchSnapshot<Document> snapshot = snapshot(documents);
        Map<LeafKey, Map<Integer, Double>> leafScores = leafScores(snapshot);

        for (int iteration = 0; iteration < 100; iteration++) {
            Spec spec = randomSpec(random, 3);
            boolean filtered = random.nextBoolean();
            int limit = List.of(1, 3, 10, 100).get(random.nextInt(4));
            SearchRequest.Builder<Document> builder = SearchRequest.<Document>builder()
                    .query(spec.query())
                    .limit(limit);
            if (filtered) {
                builder.filter(Query.eq(CATEGORY, "guide"));
            }
            SearchRequest<Document> request = builder.build();
            SearchPlan<Document> plan = new SearchPlanner<Document>(
                    new CandidatePlanner<>()).plan(
                            RankedSearchInput.from(snapshot, request)
                    );

            for (Document document : documents) {
                Eval expectedRanked = spec.evaluate(document.id(), leafScores);
                if (expectedRanked.matched()) {
                    assertTrue(
                            plan.root().candidates().get(document.id()),
                            "candidate false negative at iteration " + iteration
                                    + ": " + spec
                    );
                }
                ScoreMatch actualRanked = plan.root().evaluate(document.id());
                assertEquals(
                        expectedRanked.matched(),
                        actualRanked.matched(),
                        "ranked match mismatch at iteration " + iteration
                                + ": " + spec
                );
                assertEquals(
                        expectedRanked.matched() ? expectedRanked.score() : 0.0,
                        actualRanked.score(),
                        "ranked score mismatch at iteration " + iteration
                                + ": " + spec
                );

                boolean filterMatched = !filtered
                        || document.category().equals("guide");
                SearchExplanation<Document> explanation =
                        new ExplainExecutor<Document>().explain(
                                plan,
                                document.id(),
                                document
                        );
                assertEquals(
                        expectedRanked.matched() && filterMatched,
                        explanation.matched(),
                        "Explain match mismatch at iteration " + iteration
                                + ": " + spec
                );
                assertEquals(
                        explanation.matched() ? expectedRanked.score() : 0.0,
                        explanation.score(),
                        "Explain score mismatch at iteration " + iteration
                                + ": " + spec
                );
            }

            List<Expected> expected = documents.stream()
                    .filter(document -> !filtered || document.category().equals("guide"))
                    .map(document -> new Expected(
                            document.id(),
                            spec.evaluate(document.id(), leafScores)
                    ))
                    .filter(value -> value.result().matched())
                    .sorted(Comparator
                            .comparingDouble((Expected value) -> value.result().score())
                            .reversed()
                            .thenComparingInt(Expected::id))
                    .limit(limit)
                    .toList();

            List<SearchHit<Document>> actual = new SearchExecutor<Document>()
                    .execute(plan);
            assertEquals(
                    expected.stream().map(Expected::id).toList(),
                    actual.stream().map(hit -> hit.document().id()).toList(),
                    "document mismatch at iteration " + iteration + ": " + spec
            );
            assertEquals(
                    expected.stream().map(value -> value.result().score()).toList(),
                    actual.stream().map(SearchHit::score).toList(),
                    "score mismatch at iteration " + iteration + ": " + spec
            );
        }
    }

    private static Spec randomSpec(Random random, int depth) {
        if (depth == 0 || random.nextInt(4) == 0) {
            return new LeafSpec(
                    random.nextBoolean() ? FieldKind.TITLE : FieldKind.BODY,
                    TERMS[random.nextInt(TERMS.length)]
            );
        }
        if (random.nextInt(3) == 0) {
            return new BoostSpec(
                    randomSpec(random, depth - 1),
                    BOOSTS[random.nextInt(BOOSTS.length)]
            );
        }

        int mustCount = random.nextInt(3);
        int shouldCount = random.nextInt(3);
        if (mustCount == 0 && shouldCount == 0) {
            shouldCount = 1;
        }
        List<Spec> must = new ArrayList<>(mustCount);
        List<Spec> should = new ArrayList<>(shouldCount);
        for (int index = 0; index < mustCount; index++) {
            must.add(randomSpec(random, depth - 1));
        }
        for (int index = 0; index < shouldCount; index++) {
            should.add(randomSpec(random, depth - 1));
        }
        Integer explicitMinimum = null;
        if (random.nextBoolean()) {
            explicitMinimum = must.isEmpty()
                    ? 1 + random.nextInt(should.size())
                    : random.nextInt(should.size() + 1);
        }
        return new BoolSpec(must, should, explicitMinimum);
    }

    private static Map<LeafKey, Map<Integer, Double>> leafScores(
            SearchSnapshot<Document> snapshot
    ) {
        Map<LeafKey, Map<Integer, Double>> result = new HashMap<>();
        for (FieldKind field : FieldKind.values()) {
            for (String term : TERMS) {
                List<SearchHit<Document>> hits = SearchExecutionAccess.search(
                        snapshot,
                        SearchRequest.<Document>builder()
                                .query(SearchQueries.text(field.textField(), term))
                                .limit(100)
                                .build(),
                        new CandidatePlanner<>()
                ).hits();
                Map<Integer, Double> scores = new HashMap<>();
                for (SearchHit<Document> hit : hits) {
                    scores.put(hit.document().id(), hit.score());
                }
                result.put(new LeafKey(field, term), Map.copyOf(scores));
            }
        }
        return Map.copyOf(result);
    }

    private static List<Document> randomDocuments(Random random, int count) {
        List<Document> documents = new ArrayList<>(count);
        String[] indexedTerms = {"java", "search", "engine", "snapshot"};
        for (int id = 0; id < count; id++) {
            documents.add(new Document(
                    id,
                    randomText(random, indexedTerms, 1 + random.nextInt(3)),
                    randomText(random, indexedTerms, 1 + random.nextInt(6)),
                    random.nextBoolean() ? "guide" : "reference"
            ));
        }
        return List.copyOf(documents);
    }

    private static String randomText(
            Random random,
            String[] terms,
            int count
    ) {
        StringBuilder text = new StringBuilder();
        for (int index = 0; index < count; index++) {
            if (!text.isEmpty()) {
                text.append(' ');
            }
            text.append(terms[random.nextInt(terms.length)]);
        }
        return text.toString();
    }

    private static SearchSnapshot<Document> snapshot(List<Document> documents) {
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(TITLE_TEXT),
                IndexDefinition.text(BODY_TEXT),
                IndexDefinition.equality(CATEGORY)
        ));
        for (Document document : documents) {
            snapshot = snapshot.add(document.id(), document);
        }
        return snapshot;
    }

    private sealed interface Spec permits LeafSpec, BoolSpec, BoostSpec {
        SearchQuery<Document> query();

        Eval evaluate(int id, Map<LeafKey, Map<Integer, Double>> leafScores);
    }

    private record LeafSpec(FieldKind field, String term) implements Spec {
        @Override
        public SearchQuery<Document> query() {
            return SearchQueries.text(field.textField(), term);
        }

        @Override
        public Eval evaluate(
                int id,
                Map<LeafKey, Map<Integer, Double>> leafScores
        ) {
            Double score = leafScores.get(new LeafKey(field, term)).get(id);
            return score == null ? Eval.NO_MATCH : new Eval(true, score);
        }
    }

    private record BoolSpec(
            List<Spec> must,
            List<Spec> should,
            Integer explicitMinimum
    ) implements Spec {
        BoolSpec {
            must = List.copyOf(must);
            should = List.copyOf(should);
        }

        @Override
        public SearchQuery<Document> query() {
            SearchQueries.BoolBuilder<Document> builder = SearchQueries.bool();
            must.forEach(child -> builder.must(child.query()));
            should.forEach(child -> builder.should(child.query()));
            if (explicitMinimum != null) {
                builder.minimumShouldMatch(explicitMinimum);
            }
            return builder.build();
        }

        @Override
        public Eval evaluate(
                int id,
                Map<LeafKey, Map<Integer, Double>> leafScores
        ) {
            List<V31TestReference.Evaluation> required = must.stream()
                    .map(child -> reference(child.evaluate(id, leafScores)))
                    .toList();
            List<V31TestReference.Evaluation> optional = should.stream()
                    .map(child -> reference(child.evaluate(id, leafScores)))
                    .toList();
            V31TestReference.Evaluation result = V31TestReference.evaluateBool(
                    required,
                    optional,
                    explicitMinimum
            );
            return new Eval(result.matched(), result.score());
        }

        private static V31TestReference.Evaluation reference(Eval value) {
            return new V31TestReference.Evaluation(
                    value.matched(),
                    value.score()
            );
        }
    }

    private record BoostSpec(Spec child, double multiplier) implements Spec {
        @Override
        public SearchQuery<Document> query() {
            return child.query().boost(multiplier);
        }

        @Override
        public Eval evaluate(
                int id,
                Map<LeafKey, Map<Integer, Double>> leafScores
        ) {
            Eval result = child.evaluate(id, leafScores);
            return result.matched()
                    ? new Eval(true, result.score() * multiplier)
                    : Eval.NO_MATCH;
        }
    }

    private enum FieldKind {
        TITLE(TITLE_TEXT),
        BODY(BODY_TEXT);

        private final TextField<Document> textField;

        FieldKind(TextField<Document> textField) {
            this.textField = textField;
        }

        TextField<Document> textField() {
            return textField;
        }
    }

    private record LeafKey(FieldKind field, String term) {
    }

    private record Eval(boolean matched, double score) {
        private static final Eval NO_MATCH = new Eval(false, 0.0);
    }

    private record Expected(int id, Eval result) {
    }

    private record Document(int id, String title, String body, String category) {
    }
}
