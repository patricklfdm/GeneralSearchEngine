package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.RangePlanningMode;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;
import org.junit.jupiter.api.Test;

class V3SearchEngineTest {
    private static final Field<Article, Integer> ID =
            Field.of("id", Integer.class, Article::id);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void builtInEngineOverridesAndExecutesTheV3Capability() throws Exception {
        assertTrue(SnapshotSearchEngine.class
                .getDeclaredMethod("search", SearchRequest.class)
                .getReturnType() == SearchResult.class);
        assertTrue(SnapshotSearchEngine.class
                .getDeclaredMethod(
                        "explain",
                        SearchRequest.class,
                        Object.class
                )
                .getReturnType() == java.util.Optional.class);

        Article first = new Article(1, "java java");
        Article second = new Article(2, "java search");
        try (SearchEngine<Integer, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(TEXT))
                .build()) {
            engine.addAll(List.of(first, second)).join();
            SearchRequest<Article> request = SearchRequest.of(
                    SearchQueries.text(TEXT, "java"));

            assertEquals(
                    engine.searchTopK(RankedSearchRequest.of(
                            TextScoringQuery.of(TEXT, "java"),
                            10
                    )),
                    engine.search(request).hits()
            );
            assertThrows(
                    NullPointerException.class,
                    () -> engine.search((SearchRequest<Article>) null)
            );
        }
    }

    @Test
    void requestRemainsBoundToSnapshotCapturedBeforeAnalysis() throws Exception {
        CountDownLatch queryEntered = new CountDownLatch(1);
        CountDownLatch releaseQuery = new CountDownLatch(1);
        AtomicBoolean blockQuery = new AtomicBoolean();
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                if (text.equals("blocked-query") && blockQuery.get()) {
                    queryEntered.countDown();
                    await(releaseQuery);
                    return List.of(new AnalyzedToken("java", 1));
                }
                return Analyzer.super.analyzeWithPositions(text);
            }
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        Article original = new Article(1, "java");
        Article updated = new Article(1, "other");

        try (SearchEngine<Integer, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(text))
                .build()) {
            engine.add(original).join();
            blockQuery.set(true);
            CompletableFuture<SearchResult<Article>> result = CompletableFuture
                    .supplyAsync(() -> engine.search(SearchRequest.of(
                            SearchQueries.text(text, "blocked-query"))));

            assertTrue(queryEntered.await(5, TimeUnit.SECONDS));
            engine.update(updated).join();
            releaseQuery.countDown();

            assertEquals(
                    List.of(original),
                    result.get(5, TimeUnit.SECONDS).hits().stream()
                            .map(hit -> hit.document())
                            .toList()
            );
            assertTrue(engine.search(SearchRequest.of(
                    SearchQueries.text(text, "java"))).hits().isEmpty());
        }
    }

    @Test
    void crossFieldCompositionUsesOneSnapshotDuringConcurrentPublication()
            throws Exception {
        Field<Place, Integer> id = Field.of("id", Integer.class, Place::id);
        Field<Place, String> city = Field.of("city", String.class, Place::city);
        Field<Place, String> description = Field.of(
                "description",
                String.class,
                Place::description
        );
        CountDownLatch queryEntered = new CountDownLatch(1);
        CountDownLatch releaseQuery = new CountDownLatch(1);
        AtomicBoolean blockQuery = new AtomicBoolean();
        Analyzer blocking = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                if (text.equals("blocked-temple") && blockQuery.get()) {
                    queryEntered.countDown();
                    await(releaseQuery);
                    return List.of(new AnalyzedToken("temple", 1));
                }
                return Analyzer.super.analyzeWithPositions(text);
            }
        };
        TextField<Place> cityText = TextField.of(city, Analyzer.simple());
        TextField<Place> descriptionText = TextField.of(description, blocking);
        Place original = new Place(1, "Tokyo", "historic temple");
        Place updated = new Place(1, "Paris", "modern museum");

        try (SearchEngine<Integer, Place> engine = SearchEngine
                .builder(Place.class, id)
                .index(IndexDefinition.text(cityText))
                .index(IndexDefinition.text(descriptionText))
                .build()) {
            engine.add(original).join();
            blockQuery.set(true);
            CompletableFuture<SearchResult<Place>> result = CompletableFuture
                    .supplyAsync(() -> engine.search(SearchRequest.of(
                            SearchQueries.<Place>bool()
                                    .must(SearchQueries.text(cityText, "Tokyo"))
                                    .must(SearchQueries.text(
                                            descriptionText,
                                            "blocked-temple"
                                    ))
                                    .build()
                    )));

            assertTrue(queryEntered.await(5, TimeUnit.SECONDS));
            engine.update(updated).join();
            releaseQuery.countDown();

            assertEquals(
                    List.of(original),
                    result.get(5, TimeUnit.SECONDS).hits().stream()
                            .map(hit -> hit.document())
                            .toList()
            );
        }
    }

    @Test
    void configuredPlannerGovernsBothV2AndV3RankedPaths() {
        AtomicInteger rangeMatches = new AtomicInteger();
        Field<Article, Integer> identifier = Field.of(
                "identifier",
                Integer.class,
                article -> {
                    rangeMatches.incrementAndGet();
                    return article.id();
                }
        );
        Query<Article> filter = Query.between(identifier, 1, 1);
        try (SearchEngine<Integer, Article> engine = SearchEngine
                .builder(Article.class, ID)
                .index(IndexDefinition.text(TEXT))
                .index(IndexDefinition.range(identifier))
                .plannerConfig(new PlannerConfig(RangePlanningMode.FORCE_SCAN))
                .build()) {
            engine.addAll(List.of(
                    new Article(1, "java"),
                    new Article(2, "java"),
                    new Article(3, "java")
            )).join();

            rangeMatches.set(0);
            assertEquals(1, engine.search(SearchRequest.<Article>builder()
                    .query(SearchQueries.text(TEXT, "java"))
                    .filter(filter)
                    .build()).hits().size());
            assertEquals(3, rangeMatches.get());

            rangeMatches.set(0);
            assertEquals(1, engine.searchTopK(RankedSearchRequest.filtered(
                    TextScoringQuery.of(TEXT, "java"),
                    filter,
                    10
            )).size());
            assertEquals(3, rangeMatches.get());
        }
    }

    private static void await(CountDownLatch latch) {
        try {
            if (!latch.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("timed out waiting to release query analysis");
            }
        } catch (InterruptedException failure) {
            Thread.currentThread().interrupt();
            throw new AssertionError("query analysis interrupted", failure);
        }
    }

    private record Article(int id, String body) {
    }

    private record Place(int id, String city, String description) {
    }
}
