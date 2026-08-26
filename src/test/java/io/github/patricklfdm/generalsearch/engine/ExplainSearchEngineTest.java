package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.ExplanationNode;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import org.junit.jupiter.api.Test;

class ExplainSearchEngineTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> TITLE =
            Field.of("title", String.class, Article::title);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final TextField<Article> TITLE_TEXT =
            TextField.of(TITLE, Analyzer.simple());
    private static final TextField<Article> BODY_TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void distinguishesMissingNonMatchingAndMatchingDocuments() {
        try (SearchEngine<Long, Article> engine = engine()) {
            Article strongest = new Article(
                    1L,
                    "java java",
                    "quiet restaurant district",
                    "guide"
            );
            Article outsideTopOne = new Article(
                    2L,
                    "java",
                    "quiet museum district",
                    "reference"
            );
            Article nonMatching = new Article(
                    3L,
                    "other",
                    "coastal resort",
                    "guide"
            );
            engine.addAll(List.of(strongest, outsideTopOne, nonMatching)).join();

            SearchRequest<Article> limited = SearchRequest.<Article>builder()
                    .query(SearchQueries.text(TITLE_TEXT, "java"))
                    .limit(1)
                    .bm25(new Bm25Config(1.4, 0.6))
                    .build();
            SearchRequest<Article> complete = SearchRequest.<Article>builder()
                    .query(SearchQueries.text(TITLE_TEXT, "java"))
                    .limit(10)
                    .bm25(new Bm25Config(1.4, 0.6))
                    .build();

            assertEquals(List.of(1L), engine.search(limited).hits().stream()
                    .map(hit -> hit.document().id())
                    .toList());
            double expectedOutsideScore = engine.search(complete).hits().stream()
                    .filter(hit -> hit.document().id() == 2L)
                    .findFirst()
                    .orElseThrow()
                    .score();

            SearchExplanation<Article> matching = engine.explain(limited, 2L)
                    .orElseThrow();
            assertSame(outsideTopOne, matching.document());
            assertTrue(matching.matched());
            assertEquals(expectedOutsideScore, matching.score());
            assertEquals(matching.matched(), matching.detail().matched());
            assertEquals(matching.score(), matching.detail().score());

            SearchExplanation<Article> failed = engine.explain(limited, 3L)
                    .orElseThrow();
            assertSame(nonMatching, failed.document());
            assertFalse(failed.matched());
            assertEquals(0.0, failed.score());
            assertTrue(engine.explain(limited, 99L).isEmpty());

            String diagnostic = descriptions(matching.detail());
            assertTrue(diagnostic.contains("TEXT field=\"title\""));
            assertTrue(diagnostic.contains("term=\"java\""));
            assertTrue(diagnostic.contains("tf=1"));
            assertTrue(diagnostic.contains("df=2"));
            assertTrue(diagnostic.contains("N=3"));
            assertTrue(diagnostic.contains("k1=1.4"));
            assertTrue(diagnostic.contains("b=0.6"));
        }
    }

    @Test
    void explainsFilterFailureWithoutDiscardingRankedScore() {
        try (SearchEngine<Long, Article> engine = engine()) {
            Article rejected = new Article(
                    1L,
                    "java",
                    "quiet restaurant district",
                    "reference"
            );
            engine.add(rejected).join();
            SearchRequest<Article> request = SearchRequest.<Article>builder()
                    .query(SearchQueries.text(TITLE_TEXT, "java"))
                    .filter(Query.eq(CATEGORY, "guide"))
                    .build();

            SearchExplanation<Article> explanation = engine.explain(request, 1L)
                    .orElseThrow();
            assertFalse(explanation.matched());
            assertEquals(0.0, explanation.score());
            assertEquals(2, explanation.detail().children().size());
            ExplanationNode ranked = explanation.detail().children().get(0);
            ExplanationNode filter = explanation.detail().children().get(1);
            assertTrue(ranked.matched());
            assertTrue(ranked.score() > 0.0);
            assertFalse(filter.matched());
            assertEquals(0.0, filter.score());
            assertTrue(filter.description().contains("did not match"));
        }
    }

    @Test
    void explainsPhraseFuzzyBoolAndBoostComposition() {
        try (SearchEngine<Long, Article> engine = engine()) {
            Article target = new Article(
                    1L,
                    "travel",
                    "quiet restaurant district",
                    "guide"
            );
            engine.addAll(List.of(
                    target,
                    new Article(2L, "travel", "quiet museum", "guide")
            )).join();
            SearchRequest<Article> request = SearchRequest.of(
                    SearchQueries.<Article>bool()
                            .must(SearchQueries.phrase(
                                    BODY_TEXT,
                                    "quiet restaurant"
                            ))
                            .should(SearchQueries.fuzzy(
                                    BODY_TEXT,
                                    "restarant"
                            ).boost(2.0))
                            .build()
            );

            double expected = engine.search(request).hits().getFirst().score();
            SearchExplanation<Article> explanation = engine.explain(request, 1L)
                    .orElseThrow();
            assertTrue(explanation.matched());
            assertEquals(expected, explanation.score());
            String diagnostic = descriptions(explanation.detail());
            assertTrue(diagnostic.contains("BOOL ranked query"));
            assertTrue(diagnostic.contains("MUST clause"));
            assertTrue(diagnostic.contains("PHRASE field=\"body\""));
            assertTrue(diagnostic.contains("relative-position pattern matched"));
            assertTrue(diagnostic.contains("SHOULD clause"));
            assertTrue(diagnostic.contains("BOOST multiplier=2.0"));
            assertTrue(diagnostic.contains("FUZZY field=\"body\""));
            assertTrue(diagnostic.contains("selected term=\"restaurant\""));
            assertTrue(diagnostic.contains("editDistance=1"));
            assertTrue(diagnostic.contains("similarity=0.9"));
        }
    }

    @Test
    void keepsMissingIdAndEmptyAnalysisPrecedence() {
        try (SearchEngine<Long, Article> engine = engine()) {
            engine.add(new Article(1L, "java", "body", "guide")).join();
            TextField<Article> competing = TextField.of(TITLE, Analyzer.simple());
            SearchRequest<Article> missingIndex = SearchRequest.of(
                    SearchQueries.text(competing, "java")
            );

            assertTrue(engine.explain(missingIndex, 99L).isEmpty());
            assertThrows(
                    IllegalStateException.class,
                    () -> engine.explain(missingIndex, 1L)
            );

            SearchRequest<Article> empty = SearchRequest.of(
                    SearchQueries.text(competing, "!!!")
            );
            SearchExplanation<Article> explanation = engine.explain(empty, 1L)
                    .orElseThrow();
            assertFalse(explanation.matched());
            assertEquals(0.0, explanation.score());
            assertTrue(descriptions(explanation.detail())
                    .contains("analysis produced no scoring terms"));
        }
    }

    @Test
    void sharesAnalyzerValidationAndExceptionBehaviorWithSearch() {
        AtomicInteger invocations = new AtomicInteger();
        RuntimeException sentinel = new RuntimeException("sentinel");
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<io.github.patricklfdm.generalsearch.analysis.Token> analyze(
                    String text
            ) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                if (text.equals("bad")) {
                    invocations.incrementAndGet();
                    return null;
                }
                if (text.equals("boom")) {
                    throw sentinel;
                }
                return Analyzer.super.analyzeWithPositions(text);
            }
        };
        TextField<Article> text = TextField.of(TITLE, analyzer);
        try (SearchEngine<Long, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(text))
                .build()) {
            engine.add(new Article(1L, "java", "body", "guide")).join();
            SearchRequest<Article> malformed = SearchRequest.of(
                    SearchQueries.text(text, "bad")
            );

            assertTrue(engine.explain(malformed, 99L).isEmpty());
            assertEquals(0, invocations.get());
            IllegalArgumentException explainFailure = assertThrows(
                    IllegalArgumentException.class,
                    () -> engine.explain(malformed, 1L)
            );
            IllegalArgumentException searchFailure = assertThrows(
                    IllegalArgumentException.class,
                    () -> engine.search(malformed)
            );
            assertEquals(searchFailure.getMessage(), explainFailure.getMessage());
            assertEquals(2, invocations.get());

            SearchRequest<Article> throwing = SearchRequest.of(
                    SearchQueries.text(text, "boom")
            );
            assertSame(sentinel, assertThrows(
                    RuntimeException.class,
                    () -> engine.explain(throwing, 1L)
            ));
        }
    }

    private static SearchEngine<Long, Article> engine() {
        return SearchEngine.builder(Article.class, ID)
                .index(IndexDefinition.text(TITLE_TEXT))
                .index(IndexDefinition.text(BODY_TEXT))
                .index(IndexDefinition.equality(CATEGORY))
                .build();
    }

    private static String descriptions(ExplanationNode root) {
        List<String> descriptions = new ArrayList<>();
        collect(root, descriptions);
        return String.join("\n", descriptions);
    }

    private static void collect(
            ExplanationNode node,
            List<String> descriptions
    ) {
        descriptions.add(node.description());
        node.children().forEach(child -> collect(child, descriptions));
    }

    private record Article(
            long id,
            String title,
            String body,
            String category
    ) {
    }
}
