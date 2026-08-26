package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import java.util.List;
import java.util.Random;
import java.util.concurrent.atomic.AtomicInteger;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.PlannerConfig;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.RangePlanningMode;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.RankedSearcher;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class SearchPipelineTest {
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void executesDirectTextWithFiltersLimitsAndCustomBm25() {
        Article first = new Article(0, "java java search", "guide");
        Article second = new Article(1, "java engine", "reference");
        Article third = new Article(2, "java", "guide");
        SearchSnapshot<Article> snapshot = snapshot().add(0, first)
                .add(1, second)
                .add(2, third);
        Bm25Config config = new Bm25Config(0.8, 0.3);
        SearchRequest<Article> request = SearchRequest.<Article>builder()
                .query(SearchQueries.text(TEXT, "java java unknown"))
                .filter(Query.eq(CATEGORY, "guide"))
                .limit(1)
                .bm25(config)
                .build();

        List<SearchHit<Article>> actual = execute(snapshot, request);
        List<SearchHit<Article>> legacy = new RankedSearcher<Article>().search(
                snapshot,
                RankedSearchRequest.filtered(
                        TextScoringQuery.of(TEXT, "java java unknown"),
                        Query.eq(CATEGORY, "guide"),
                        1,
                        config
                )
        );

        assertEquals(legacy, actual);
        assertEquals(List.of(first), documents(actual));
    }

    @Test
    void preservesEmptyUnknownAndCanonicalIndexPrecedence() {
        SearchSnapshot<Article> noIndex = new SearchSnapshot<>(List.of());
        assertTrue(execute(noIndex, request(TEXT, "---")).isEmpty());

        IllegalStateException missing = assertThrows(
                IllegalStateException.class,
                () -> execute(noIndex, request(TEXT, "java"))
        );
        assertTrue(missing.getMessage().contains("body"));

        TextField<Article> competing = TextField.of(BODY, Analyzer.simple());
        SearchSnapshot<Article> competingIndex = new SearchSnapshot<Article>(
                List.of(IndexDefinition.text(competing)))
                .add(0, new Article(0, "java", "guide"));
        assertThrows(
                IllegalStateException.class,
                () -> execute(competingIndex, request(TEXT, "java"))
        );

        SearchSnapshot<Article> indexed = snapshot()
                .add(0, new Article(0, "java", "guide"));
        assertTrue(execute(indexed, request(TEXT, "unknown")).isEmpty());
    }

    @Test
    void rejectsMultiTermFuzzyBeforeIndexWork() {
        TextField<Article> field = TextField.of(BODY, Analyzer.simple());
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> execute(
                        new SearchSnapshot<>(List.of()),
                        SearchRequest.of(SearchQueries.fuzzy(field, "java search"))
                )
        );
        assertTrue(failure.getMessage().contains("exactly one"));
    }

    @Test
    void usesNativePositionedAnalysisExactlyOnceAndDeduplicatesTerms() {
        AtomicInteger queryCalls = new AtomicInteger();
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of(new Token("legacy"));
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                if (text.equals("query")) {
                    queryCalls.incrementAndGet();
                    return List.of(
                            new AnalyzedToken("target", 4),
                            new AnalyzedToken("target", 0)
                    );
                }
                return List.of(new AnalyzedToken(text, 1));
            }
        };
        TextField<Article> field = TextField.of(BODY, analyzer);
        Article matching = new Article(0, "target", "guide");
        Article other = new Article(1, "other", "guide");
        SearchSnapshot<Article> snapshot = new SearchSnapshot<Article>(
                List.of(IndexDefinition.text(field)))
                .add(0, matching)
                .add(1, other);

        assertEquals(
                List.of(matching),
                documents(execute(snapshot, request(field, "query")))
        );
        assertEquals(1, queryCalls.get());
    }

    @Test
    void validatesCompletePositionedOutputAndPreservesAnalyzerFailure() {
        assertInvalidAnalysis(text -> null, "null token list");
        assertInvalidAnalysis(
                text -> Arrays.asList((AnalyzedToken) null),
                "null token at index 0"
        );
        assertInvalidAnalysis(
                text -> List.of(new AnalyzedToken("term", 0)),
                "non-positive first position increment"
        );
        assertInvalidAnalysis(
                text -> List.of(
                        new AnalyzedToken("first", Integer.MAX_VALUE),
                        new AnalyzedToken("second", 2)
                ),
                "overflowed logical position"
        );

        RuntimeException expected = new RuntimeException("analyzer failure");
        Analyzer throwing = text -> {
            throw expected;
        };
        RuntimeException actual = assertThrows(
                RuntimeException.class,
                () -> execute(
                        new SearchSnapshot<>(List.of()),
                        request(TextField.of(BODY, throwing), "query")
                )
        );
        assertSame(expected, actual);
    }

    @Test
    void alwaysVerifiesIndexedAndUnindexedFilterTruth() {
        AtomicInteger indexedMatches = new AtomicInteger();
        Field<Article, String> countingCategory = Field.of(
                "category",
                String.class,
                article -> {
                    indexedMatches.incrementAndGet();
                    return article.category();
                }
        );
        Article guide = new Article(0, "java", "guide");
        Article reference = new Article(1, "java", "reference");
        SearchSnapshot<Article> indexed = new SearchSnapshot<Article>(List.of(
                IndexDefinition.text(TEXT),
                IndexDefinition.equality(countingCategory)
        )).add(0, guide).add(1, reference);
        indexedMatches.set(0);

        SearchRequest<Article> indexedRequest = SearchRequest.<Article>builder()
                .query(SearchQueries.text(TEXT, "java"))
                .filter(Query.eq(countingCategory, "guide"))
                .build();
        assertEquals(List.of(guide), documents(execute(indexed, indexedRequest)));
        assertEquals(1, indexedMatches.get());

        AtomicInteger unindexedMatches = new AtomicInteger();
        Query<Article> unindexed = article -> {
            unindexedMatches.incrementAndGet();
            return article.category().equals("guide");
        };
        SearchRequest<Article> unindexedRequest = SearchRequest.<Article>builder()
                .query(SearchQueries.text(TEXT, "java"))
                .filter(unindexed)
                .build();
        assertEquals(List.of(guide), documents(execute(indexed, unindexedRequest)));
        assertEquals(2, unindexedMatches.get());

        SearchRequest<Article> matchAll = SearchRequest.<Article>builder()
                .query(SearchQueries.text(TEXT, "java"))
                .filter(Query.matchAll())
                .build();
        assertEquals(2, execute(indexed, matchAll).size());

        SearchRequest<Article> matchNone = SearchRequest.<Article>builder()
                .query(SearchQueries.text(TEXT, "java"))
                .filter(article -> false)
                .build();
        assertTrue(execute(indexed, matchNone).isEmpty());
    }

    @Test
    void planOwnsTheExactSnapshotAndExecutionAcceptsNoReplacement() {
        Article original = new Article(0, "java", "guide");
        SearchSnapshot<Article> first = snapshot().add(0, original);
        SearchSnapshot<Article> changed = first.update(
                0,
                new Article(0, "other", "guide")
        );
        RankedSearchInput<Article> input = RankedSearchInput.from(
                first,
                request(TEXT, "java")
        );
        SearchPlan<Article> plan = new SearchPlanner<Article>(new CandidatePlanner<>())
                .plan(input);

        assertSame(first, plan.snapshot());
        assertEquals(List.of(original), documents(new SearchExecutor<Article>()
                .execute(plan)));
        assertTrue(execute(changed, request(TEXT, "java")).isEmpty());
    }

    @Test
    void ordersEqualScoresByAscendingInternalDocumentId() {
        Article later = new Article(8, "same term", "guide");
        Article earlier = new Article(2, "same term", "guide");
        SearchSnapshot<Article> snapshot = snapshot()
                .add(8, later)
                .add(2, earlier);

        List<SearchHit<Article>> hits = execute(
                snapshot,
                SearchRequest.<Article>builder()
                        .query(SearchQueries.text(TEXT, "same"))
                        .limit(100)
                        .build()
        );

        assertEquals(List.of(earlier, later), documents(hits));
        assertEquals(hits.get(0).score(), hits.get(1).score());
    }

    @Test
    void legacyAdapterCopiesFrozenTermsWithoutReanalysis() {
        AtomicInteger calls = new AtomicInteger();
        Analyzer analyzer = text -> {
            calls.incrementAndGet();
            return Analyzer.simple().analyze(text);
        };
        TextField<Article> field = TextField.of(BODY, analyzer);
        SearchSnapshot<Article> snapshot = new SearchSnapshot<Article>(
                List.of(IndexDefinition.text(field)))
                .add(0, new Article(0, "java", "guide"));
        TextScoringQuery<Article> scoring = TextScoringQuery.of(field, "java");
        int callsAfterConstruction = calls.get();

        List<SearchHit<Article>> hits = new RankedSearcher<Article>(
                new CandidatePlanner<>()).search(
                snapshot,
                RankedSearchRequest.of(scoring, 10)
        );

        assertEquals(1, hits.size());
        assertEquals(callsAfterConstruction, calls.get());
    }

    @Test
    void directSearcherHonorsTheInjectedPlannerConfiguration() {
        AtomicInteger rangeMatches = new AtomicInteger();
        Field<Article, Integer> identifier = Field.of(
                "identifier",
                Integer.class,
                article -> {
                    rangeMatches.incrementAndGet();
                    return article.id();
                }
        );
        Article first = new Article(0, "java", "guide");
        SearchSnapshot<Article> snapshot = new SearchSnapshot<Article>(List.of(
                IndexDefinition.text(TEXT),
                IndexDefinition.range(identifier)
        )).add(0, first)
                .add(1, new Article(1, "java", "guide"))
                .add(2, new Article(2, "java", "guide"));
        RankedSearchRequest<Article> request = RankedSearchRequest.filtered(
                TextScoringQuery.of(TEXT, "java"),
                Query.between(identifier, 0, 0),
                10
        );

        rangeMatches.set(0);
        List<SearchHit<Article>> indexed = new RankedSearcher<Article>(
                new CandidatePlanner<>(new PlannerConfig(
                        RangePlanningMode.FORCE_INDEX)))
                .search(snapshot, request);
        assertEquals(List.of(first), documents(indexed));
        assertEquals(1, rangeMatches.get());

        rangeMatches.set(0);
        List<SearchHit<Article>> scanned = new RankedSearcher<Article>(
                new CandidatePlanner<>(new PlannerConfig(
                        RangePlanningMode.FORCE_SCAN)))
                .search(snapshot, request);
        assertEquals(indexed, scanned);
        assertEquals(3, rangeMatches.get());
    }

    @Test
    void v2AndV3RemainExactlyEqualAcrossDeterministicMutations() {
        Random random = new Random(30_003);
        SearchSnapshot<Article> snapshot = snapshot();
        Article[] active = new Article[80];
        RankedSearcher<Article> legacySearcher = new RankedSearcher<>(
                new CandidatePlanner<>());
        String[] terms = {"java", "search", "engine", "index", "snapshot"};
        String[] categories = {"guide", "reference"};

        for (int operation = 0; operation < 240; operation++) {
            int docId = random.nextInt(active.length);
            if (active[docId] == null) {
                Article article = randomArticle(docId, random, terms, categories);
                active[docId] = article;
                snapshot = snapshot.add(docId, article);
            } else if (random.nextInt(6) == 0) {
                active[docId] = null;
                snapshot = snapshot.remove(docId);
            } else {
                Article article = randomArticle(docId, random, terms, categories);
                active[docId] = article;
                snapshot = snapshot.update(docId, article);
            }

            if (operation % 8 == 0) {
                String queryText = randomQuery(random, terms);
                int limit = List.of(1, 5, 100).get(random.nextInt(3));
                Bm25Config config = random.nextBoolean()
                        ? Bm25Config.DEFAULT
                        : new Bm25Config(0.9, 0.25);
                Query<Article> filter = random.nextBoolean()
                        ? null
                        : Query.eq(CATEGORY, categories[random.nextInt(categories.length)]);
                SearchRequest<Article> v3 = v3Request(
                        queryText,
                        filter,
                        limit,
                        config
                );
                RankedSearchRequest<Article> v2 = v2Request(
                        queryText,
                        filter,
                        limit,
                        config
                );

                assertEquals(
                        legacySearcher.search(snapshot, v2),
                        execute(snapshot, v3),
                        "operation=" + operation
                );
            }
        }
    }

    private static void assertInvalidAnalysis(
            PositionedAnalysis analysis,
            String expectedDetail
    ) {
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return analysis.analyze(text);
            }
        };
        TextField<Article> field = TextField.of(BODY, analyzer);
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> execute(
                        new SearchSnapshot<>(List.of()),
                        request(field, "query")
                )
        );
        assertTrue(failure.getMessage().contains("body"));
        assertTrue(failure.getMessage().contains(expectedDetail));
    }

    private static SearchRequest<Article> v3Request(
            String queryText,
            Query<Article> filter,
            int limit,
            Bm25Config config
    ) {
        SearchRequest.Builder<Article> builder = SearchRequest.<Article>builder()
                .query(SearchQueries.text(TEXT, queryText))
                .limit(limit)
                .bm25(config);
        if (filter != null) {
            builder.filter(filter);
        }
        return builder.build();
    }

    private static RankedSearchRequest<Article> v2Request(
            String queryText,
            Query<Article> filter,
            int limit,
            Bm25Config config
    ) {
        TextScoringQuery<Article> scoring = TextScoringQuery.of(TEXT, queryText);
        return filter == null
                ? RankedSearchRequest.of(scoring, limit, config)
                : RankedSearchRequest.filtered(scoring, filter, limit, config);
    }

    private static Article randomArticle(
            int docId,
            Random random,
            String[] terms,
            String[] categories
    ) {
        int count = 1 + random.nextInt(6);
        StringBuilder body = new StringBuilder();
        for (int index = 0; index < count; index++) {
            if (!body.isEmpty()) {
                body.append(' ');
            }
            body.append(terms[random.nextInt(terms.length)]);
        }
        return new Article(
                docId,
                body.toString(),
                categories[random.nextInt(categories.length)]
        );
    }

    private static String randomQuery(Random random, String[] terms) {
        String first = terms[random.nextInt(terms.length)];
        String second = terms[random.nextInt(terms.length)];
        return random.nextBoolean()
                ? first + " " + second
                : first + " " + first + " unknown";
    }

    private static SearchRequest<Article> request(
            TextField<Article> field,
            String text
    ) {
        return SearchRequest.of(SearchQueries.text(field, text));
    }

    private static List<SearchHit<Article>> execute(
            SearchSnapshot<Article> snapshot,
            SearchRequest<Article> request
    ) {
        return SearchExecutionAccess.search(
                snapshot,
                request,
                new CandidatePlanner<>()
        ).hits();
    }

    private static SearchSnapshot<Article> snapshot() {
        return new SearchSnapshot<>(List.of(
                IndexDefinition.text(TEXT),
                IndexDefinition.equality(CATEGORY)
        ));
    }

    private static List<Article> documents(List<SearchHit<Article>> hits) {
        return hits.stream().map(SearchHit::document).toList();
    }

    @FunctionalInterface
    private interface PositionedAnalysis {
        List<AnalyzedToken> analyze(String text);
    }

    private record Article(int id, String body, String category) {
    }
}
