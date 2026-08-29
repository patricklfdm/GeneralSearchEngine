package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class ExplainPlanDifferentialTest {
    private static final long SEED = 0x7E11A1L;
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

    @Test
    void matchesPreparedEvaluationForEveryRankedNodeKind() {
        SearchSnapshot<Document> snapshot = snapshot();
        List<SearchQuery<Document>> queries = List.of(
                SearchQueries.text(TITLE_TEXT, "java search"),
                SearchQueries.phrase(BODY_TEXT, "quiet restaurant"),
                SearchQueries.phrase(BODY_TEXT, "quiet district", 2),
                SearchQueries.fuzzy(BODY_TEXT, "restarant"),
                SearchQueries.<Document>bool()
                        .must(SearchQueries.text(TITLE_TEXT, "java"))
                        .should(SearchQueries.fuzzy(BODY_TEXT, "restarant"))
                        .build(),
                SearchQueries.<Document>bool()
                        .should(SearchQueries.phrase(BODY_TEXT, "quiet museum"))
                        .should(SearchQueries.text(TITLE_TEXT, "travel").boost(1.5))
                        .build()
                        .boost(2.0)
        );

        for (SearchQuery<Document> query : queries) {
            assertRequestInvariant(snapshot, request(query, null));
            assertRequestInvariant(snapshot, request(
                    query,
                    Query.eq(CATEGORY, "guide")
            ));
            assertRequestInvariant(snapshot, request(
                    query,
                    document -> document.category().startsWith("ref")
            ));
        }
    }

    @Test
    void keepsFailedBoolZeroWhileRetainingPositiveShouldDiagnostics() {
        SearchSnapshot<Document> snapshot = snapshot();
        SearchQuery<Document> query = SearchQueries.<Document>bool()
                .must(SearchQueries.text(TITLE_TEXT, "missing"))
                .should(SearchQueries.text(TITLE_TEXT, "java"))
                .build();
        SearchPlan<Document> plan = plan(snapshot, request(query, null));

        ExplanationNode detail = plan.root().explain(0);
        assertFalse(detail.matched());
        assertEquals(0.0, detail.score());
        assertFalse(detail.children().get(0).matched());
        assertTrue(detail.children().get(1).matched());
        assertTrue(detail.children().get(1).score() > 0.0);
    }

    @Test
    void termChildrenRecomposeTextScoreAndRemainImmutable() {
        SearchSnapshot<Document> snapshot = snapshot();
        SearchPlan<Document> plan = plan(snapshot, request(
                SearchQueries.text(TITLE_TEXT, "java absent search java"),
                null
        ));
        ExplanationNode detail = plan.root().explain(0);

        double recomposed = 0.0;
        for (ExplanationNode child : detail.children()) {
            if (child.matched()) {
                recomposed = ScoreArithmetic.add(recomposed, child.score());
            }
        }
        assertEquals(detail.score(), recomposed);
        assertEquals(3, detail.children().size());
        assertFalse(detail.children().get(1).matched());
        assertTrue(detail.children().get(1).description().contains("term=\"absent\""));
        assertThrows(
                UnsupportedOperationException.class,
                () -> detail.children().add(detail)
        );
    }

    @Test
    void reportsBm25FactsThatReproduceTheControlledContribution() {
        SearchSnapshot<Document> snapshot = snapshot();
        Bm25Config config = new Bm25Config(1.2, 0.75);
        SearchRequest<Document> request = SearchRequest.<Document>builder()
                .query(SearchQueries.text(TITLE_TEXT, "java"))
                .bm25(config)
                .build();
        ExplanationNode term = plan(snapshot, request)
                .root()
                .explain(0)
                .children()
                .getFirst();

        int termFrequency = 1;
        int documentFrequency = 3;
        int documentCount = 6;
        int documentLength = 2;
        double averageDocumentLength = 8.0 / 6.0;
        double idf = Math.log1p(
                (documentCount - documentFrequency + 0.5)
                        / (documentFrequency + 0.5)
        );
        double normalization = config.k1() * (
                1.0 - config.b()
                        + config.b() * documentLength / averageDocumentLength
        );
        double expected = idf * (termFrequency * (config.k1() + 1.0))
                / (termFrequency + normalization);

        assertTrue(term.matched());
        assertEquals(expected, term.score());
        assertTrue(term.description().contains("tf=1"));
        assertTrue(term.description().contains("df=3"));
        assertTrue(term.description().contains("N=6"));
        assertTrue(term.description().contains("dl=2"));
        assertTrue(term.description().contains("avgdl=" + averageDocumentLength));
        assertTrue(term.description().contains("idf=" + idf));
        assertTrue(term.description().contains("contribution=" + expected));
    }

    @Test
    void randomizedRecursiveTreesKeepMatchScoreAndTreeInvariants() {
        SearchSnapshot<Document> snapshot = snapshot();
        Random random = new Random(SEED);
        for (int iteration = 0; iteration < 250; iteration++) {
            SearchQuery<Document> query = randomQuery(random, 3);
            Query<Document> filter = switch (random.nextInt(4)) {
                case 0 -> null;
                case 1 -> Query.eq(CATEGORY, "guide");
                case 2 -> Query.eq(CATEGORY, "reference");
                default -> document -> document.body().contains("quiet");
            };
            SearchRequest<Document> request = SearchRequest.<Document>builder()
                    .query(query)
                    .limit(1 + random.nextInt(20))
                    .bm25(new Bm25Config(
                            0.5 + random.nextDouble() * 2.0,
                            random.nextDouble()
                    ))
                    .build();
            if (filter != null) {
                request = SearchRequest.<Document>builder()
                        .query(query)
                        .filter(filter)
                        .limit(1 + random.nextInt(20))
                        .bm25(request.bm25())
                        .build();
            }
            SearchPlan<Document> plan = plan(snapshot, request);
            for (int docId = 0; docId < 6; docId++) {
                Document document = snapshot.get(docId);
                ScoreMatch ranked = plan.root().evaluate(docId);
                boolean filterMatched = filter == null || filter.matches(document);
                boolean expectedMatched = ranked.matched() && filterMatched;
                double expectedScore = expectedMatched ? ranked.score() : 0.0;

                SearchExplanation<Document> first = new ExplainExecutor<Document>()
                        .explain(plan, docId, document);
                SearchExplanation<Document> second = new ExplainExecutor<Document>()
                        .explain(plan, docId, document);
                assertEquals(expectedMatched, first.matched());
                assertEquals(expectedScore, first.score());
                assertTree(first.detail());
                assertEquals(render(first.detail()), render(second.detail()));
            }
        }
    }

    private static void assertRequestInvariant(
            SearchSnapshot<Document> snapshot,
            SearchRequest<Document> request
    ) {
        SearchPlan<Document> plan = plan(snapshot, request);
        Query<Document> filter = request.filter().orElse(null);
        for (int docId = 0; docId < 6; docId++) {
            Document document = snapshot.get(docId);
            ScoreMatch ranked = plan.root().evaluate(docId);
            boolean filterMatched = filter == null || filter.matches(document);
            boolean expectedMatched = ranked.matched() && filterMatched;
            double expectedScore = expectedMatched ? ranked.score() : 0.0;
            SearchExplanation<Document> actual = new ExplainExecutor<Document>()
                    .explain(plan, docId, document);
            assertEquals(expectedMatched, actual.matched());
            assertEquals(expectedScore, actual.score());
            assertTree(actual.detail());
        }
    }

    private static SearchQuery<Document> randomQuery(Random random, int depth) {
        if (depth == 0 || random.nextInt(4) == 0) {
            return randomLeaf(random);
        }
        if (random.nextBoolean()) {
            double multiplier = switch (random.nextInt(3)) {
                case 0 -> 0.5;
                case 1 -> 1.5;
                default -> 2.0;
            };
            return randomQuery(random, depth - 1).boost(multiplier);
        }
        SearchQueries.BoolBuilder<Document> builder = SearchQueries.bool();
        int mustCount = random.nextInt(3);
        int shouldCount = mustCount == 0
                ? 1 + random.nextInt(3)
                : random.nextInt(3);
        for (int index = 0; index < mustCount; index++) {
            builder.must(randomQuery(random, depth - 1));
        }
        for (int index = 0; index < shouldCount; index++) {
            builder.should(randomQuery(random, depth - 1));
        }
        return builder.build();
    }

    private static SearchQuery<Document> randomLeaf(Random random) {
        return switch (random.nextInt(6)) {
            case 0 -> SearchQueries.text(TITLE_TEXT, "java search");
            case 1 -> SearchQueries.text(TITLE_TEXT, "travel absent");
            case 2 -> SearchQueries.phrase(
                    BODY_TEXT,
                    "quiet restaurant",
                    random.nextInt(3)
            );
            case 3 -> SearchQueries.phrase(
                    BODY_TEXT,
                    "museum district",
                    random.nextInt(3)
            );
            case 4 -> SearchQueries.fuzzy(BODY_TEXT, "restarant");
            default -> SearchQueries.fuzzy(BODY_TEXT, "musuem");
        };
    }

    private static SearchRequest<Document> request(
            SearchQuery<Document> query,
            Query<Document> filter
    ) {
        SearchRequest.Builder<Document> builder = SearchRequest.<Document>builder()
                .query(query)
                .limit(100);
        if (filter != null) {
            builder.filter(filter);
        }
        return builder.build();
    }

    private static SearchPlan<Document> plan(
            SearchSnapshot<Document> snapshot,
            SearchRequest<Document> request
    ) {
        return new SearchPlanner<Document>(new CandidatePlanner<>()).plan(
                RankedSearchInput.from(snapshot, request)
        );
    }

    private static SearchSnapshot<Document> snapshot() {
        SearchSnapshot<Document> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(TITLE_TEXT),
                IndexDefinition.text(BODY_TEXT),
                IndexDefinition.equality(CATEGORY)
        ));
        List<Document> documents = List.of(
                new Document("java search", "quiet restaurant district", "guide"),
                new Document("java", "quiet museum district", "reference"),
                new Document("travel", "coastal restarant", "guide"),
                new Document("search", "museum district", "reference"),
                new Document("other", "restaurant guide", "guide"),
                new Document("java travel", "quiet resort", "other")
        );
        for (int docId = 0; docId < documents.size(); docId++) {
            snapshot = snapshot.add(docId, documents.get(docId));
        }
        return snapshot;
    }

    private static void assertTree(ExplanationNode node) {
        assertTrue(Double.isFinite(node.score()));
        assertTrue(node.score() >= 0.0);
        if (!node.matched()) {
            assertEquals(0.0, node.score());
        }
        assertFalse(node.description().contains("docId"));
        node.children().forEach(ExplainPlanDifferentialTest::assertTree);
    }

    private static String render(ExplanationNode node) {
        List<String> lines = new ArrayList<>();
        render(node, lines, 0);
        return String.join("\n", lines);
    }

    private static void render(
            ExplanationNode node,
            List<String> lines,
            int depth
    ) {
        lines.add(depth + ":" + node.matched() + ":" + node.score()
                + ":" + node.description());
        node.children().forEach(child -> render(child, lines, depth + 1));
    }

    private record Document(String title, String body, String category) {
    }
}
