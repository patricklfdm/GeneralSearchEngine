package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.Bm25Config;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class FuzzySearchTest {
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
    void appliesAutoThresholdAndBuildsTheExactCandidateUnion() {
        Article exact = new Article(1, "", "restaurant", "guide");
        Article deletion = new Article(5, "", "restarant", "guide");
        Article transposition = new Article(9, "", "restuarant", "guide");
        Article unrelated = new Article(12, "", "unrelated", "guide");
        SearchSnapshot<Article> snapshot = snapshot(
                exact,
                deletion,
                transposition,
                unrelated
        );

        SearchPlan<Article> plan = plan(
                snapshot,
                request(SearchQueries.fuzzy(BODY_TEXT, "restaurant"))
        );
        FuzzyPlan<?> fuzzy = assertInstanceOf(FuzzyPlan.class, plan.root());

        assertEquals(3, fuzzy.candidates().cardinality());
        assertTrue(fuzzy.candidates().get(1));
        assertTrue(fuzzy.candidates().get(5));
        assertTrue(fuzzy.candidates().get(9));
        assertFalse(fuzzy.candidates().get(12));
        assertEquals(
                List.of(exact, deletion, transposition),
                documents(execute(snapshot, SearchQueries.fuzzy(
                        BODY_TEXT,
                        "restaurant"
                )))
        );

        SearchSnapshot<Article> shortTerms = snapshot(
                new Article(0, "", "ab", "guide"),
                new Article(1, "", "ac", "guide"),
                new Article(2, "", "abd", "guide")
        );
        assertEquals(
                List.of(0),
                ids(execute(shortTerms, SearchQueries.fuzzy(BODY_TEXT, "ab")))
        );
        assertEquals(
                List.of(0, 1, 2),
                ids(execute(shortTerms, SearchQueries.fuzzy(BODY_TEXT, "abc")))
        );
    }

    @Test
    void givesAnExactTermAbsolutePriorityWithinEachDocument() {
        Article target = new Article(
                0,
                "",
                "restaurant restarant",
                "guide"
        );
        SearchSnapshot<Article> snapshot = snapshot(
                target,
                new Article(1, "", "restaurant filler", "guide"),
                new Article(2, "", "restaurant filler", "guide"),
                new Article(3, "", "restaurant filler", "guide"),
                new Article(4, "", "restaurant filler", "guide"),
                new Article(5, "", "restaurant filler", "guide"),
                new Article(6, "", "restaurant filler", "guide")
        );
        double exactScore = scoreOf(
                execute(snapshot, SearchQueries.text(BODY_TEXT, "restaurant")),
                0
        );
        double alternativeScore = scoreOf(
                execute(snapshot, SearchQueries.text(BODY_TEXT, "restarant")),
                0
        ) * 0.9;
        assertTrue(alternativeScore > exactScore);

        assertEquals(
                exactScore,
                scoreOf(execute(
                        snapshot,
                        SearchQueries.fuzzy(BODY_TEXT, "restaurant")
                ), 0)
        );
    }

    @Test
    void selectsTheBestNonExactScoreWithoutSummingAndBreaksTiesByTerm() {
        Article both = new Article(
                0,
                "",
                "restarant restuarant",
                "guide"
        );
        SearchSnapshot<Article> snapshot = snapshot(
                both,
                new Article(1, "", "restarant filler", "guide"),
                new Article(2, "", "restuarant filler", "guide")
        );
        double firstScore = scoreOf(
                execute(snapshot, SearchQueries.text(BODY_TEXT, "restarant")),
                0
        ) * 0.9;
        double secondScore = scoreOf(
                execute(snapshot, SearchQueries.text(BODY_TEXT, "restuarant")),
                0
        ) * 0.9;
        assertEquals(firstScore, secondScore);

        SearchPlan<Article> plan = plan(
                snapshot,
                request(SearchQueries.fuzzy(BODY_TEXT, "restaurant"))
        );
        FuzzyPlan<?> fuzzy = assertInstanceOf(FuzzyPlan.class, plan.root());
        FuzzyEvaluation evaluation = fuzzy.evaluateFuzzy(0);

        assertTrue(evaluation.result().matched());
        assertEquals(firstScore, evaluation.result().score());
        assertNotEquals(firstScore + secondScore, evaluation.result().score());
        assertEquals("restarant", evaluation.selectedTerm());
        assertEquals(List.of("restarant", "restuarant"), fuzzy.expansions()
                .stream()
                .map(FuzzyScoringExpansion::term)
                .toList());
    }

    @Test
    void composesWithTextBoostCustomBm25AndStructuredFilters() {
        Article guide = new Article(0, "java", "restarant filler", "guide");
        Article reference = new Article(
                1,
                "java",
                "restarant filler filler",
                "reference"
        );
        Article bodyOnly = new Article(
                2,
                "other",
                "restarant",
                "guide"
        );
        SearchSnapshot<Article> snapshot = snapshot(guide, reference, bodyOnly);
        Bm25Config config = new Bm25Config(0.7, 0.2);
        double titleScore = scoreOf(execute(
                snapshot,
                request(SearchQueries.text(TITLE_TEXT, "java"), config)
        ), 0);
        double fuzzyScore = scoreOf(execute(
                snapshot,
                request(SearchQueries.fuzzy(BODY_TEXT, "restaurant"), config)
        ), 0);
        SearchQuery<Article> composed = SearchQueries.<Article>bool()
                .must(SearchQueries.text(TITLE_TEXT, "java"))
                .should(SearchQueries.fuzzy(BODY_TEXT, "restaurant").boost(2.0))
                .build();
        SearchRequest<Article> filtered = SearchRequest.<Article>builder()
                .query(composed)
                .filter(Query.eq(CATEGORY, "guide"))
                .bm25(config)
                .build();

        List<SearchHit<Article>> hits = execute(snapshot, filtered);
        assertEquals(List.of(guide), documents(hits));
        assertEquals(titleScore + fuzzyScore * 2.0, hits.getFirst().score());
    }

    @Test
    void composesWithPhraseAndIndexedUnindexedAndBooleanFilters() {
        Article both = new Article(
                0,
                "quiet neighborhood",
                "restarant",
                "guide"
        );
        Article phraseOnly = new Article(
                1,
                "quiet neighborhood",
                "other",
                "reference"
        );
        Article fuzzyOnly = new Article(
                2,
                "neighborhood quiet",
                "restarant",
                "guide"
        );
        SearchSnapshot<Article> snapshot = snapshot(both, phraseOnly, fuzzyOnly);
        double phraseScore = scoreOf(execute(
                snapshot,
                SearchQueries.phrase(TITLE_TEXT, "quiet neighborhood")
        ), 0);
        double fuzzyScore = scoreOf(execute(
                snapshot,
                SearchQueries.fuzzy(BODY_TEXT, "restaurant")
        ), 0);
        SearchQuery<Article> composed = SearchQueries.<Article>bool()
                .must(SearchQueries.phrase(
                        TITLE_TEXT,
                        "quiet neighborhood"
                ))
                .should(SearchQueries.fuzzy(
                        BODY_TEXT,
                        "restaurant"
                ).boost(2.0))
                .build();
        List<SearchHit<Article>> unfiltered = execute(snapshot, composed);

        assertEquals(List.of(both, phraseOnly), documents(unfiltered));
        assertEquals(
                phraseScore + fuzzyScore * 2.0,
                unfiltered.getFirst().score()
        );

        Query<Article> unindexed = article -> article.category().equals("guide");
        List<SearchHit<Article>> unindexedHits = execute(
                snapshot,
                filtered(composed, unindexed)
        );
        assertEquals(List.of(both), documents(unindexedHits));
        assertEquals(unfiltered.getFirst().score(), unindexedHits.getFirst().score());

        Query<Article> byId = article -> article.id() == 0;
        List<SearchHit<Article>> booleanHits = execute(
                snapshot,
                filtered(composed, Query.and(
                        Query.eq(CATEGORY, "guide"),
                        byId
                ))
        );
        assertEquals(List.of(both), documents(booleanHits));
        assertEquals(unfiltered.getFirst().score(), booleanHits.getFirst().score());
    }

    @Test
    void enforcesFuzzyAnalysisCardinalityBeforeIndexLookup() {
        Analyzer duplicate = positioned(List.of(
                new AnalyzedToken("same", 1),
                new AnalyzedToken("same", 1)
        ));
        Analyzer samePositionAlternatives = positioned(List.of(
                new AnalyzedToken("first", 1),
                new AnalyzedToken("second", 0)
        ));

        for (Analyzer analyzer : List.of(duplicate, samePositionAlternatives)) {
            TextField<Article> field = TextField.of(BODY, analyzer);
            IllegalArgumentException failure = assertThrows(
                    IllegalArgumentException.class,
                    () -> execute(
                            new SearchSnapshot<>(List.of()),
                            SearchQueries.fuzzy(field, "query")
                    )
            );
            assertTrue(failure.getMessage().contains("body"));
            assertTrue(failure.getMessage().contains("exactly one"));
        }
    }

    @Test
    void validatesCompletePositionedAnalysisAndPropagatesAnalyzerFailures() {
        assertInvalidFuzzy(text -> null, "null token list");
        assertInvalidFuzzy(
                text -> Arrays.asList((AnalyzedToken) null),
                "null token at index 0"
        );
        assertInvalidFuzzy(
                text -> List.of(new AnalyzedToken("term", 0)),
                "non-positive first position increment"
        );
        assertInvalidFuzzy(
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
                        SearchQueries.fuzzy(
                                TextField.of(BODY, throwing),
                                "query"
                        )
                )
        );
        assertSame(expected, actual);
    }

    @Test
    void treatsEmptyAndNoExpansionAsMatchNoneButRequiresANonEmptyIndex() {
        TextField<Article> empty = TextField.of(BODY, positioned(List.of()));
        assertTrue(execute(
                new SearchSnapshot<>(List.of()),
                SearchQueries.fuzzy(empty, "query")
        ).isEmpty());

        IllegalStateException missing = assertThrows(
                IllegalStateException.class,
                () -> execute(
                        new SearchSnapshot<>(List.of()),
                        SearchQueries.fuzzy(BODY_TEXT, "restaurant")
                )
        );
        assertTrue(missing.getMessage().contains("body"));

        SearchSnapshot<Article> indexed = snapshot(
                new Article(0, "", "unrelated", "guide")
        );
        assertTrue(execute(
                indexed,
                SearchQueries.fuzzy(BODY_TEXT, "restaurant")
        ).isEmpty());
    }

    @Test
    void requiresCanonicalIndexesForRootMustAndShouldInLogicalOrder() {
        TextField<Article> competing = TextField.of(BODY, Analyzer.simple());
        SearchSnapshot<Article> snapshot = snapshot(
                new Article(0, "title", "restaurant", "guide")
        );

        assertMissing(snapshot, SearchQueries.fuzzy(competing, "restaurant"));
        assertMissing(snapshot, SearchQueries.<Article>bool()
                .must(SearchQueries.fuzzy(competing, "restaurant"))
                .should(SearchQueries.fuzzy(BODY_TEXT, "restaurant"))
                .build());
        assertMissing(snapshot, SearchQueries.<Article>bool()
                .must(SearchQueries.fuzzy(BODY_TEXT, "unknown"))
                .should(SearchQueries.fuzzy(competing, "restaurant"))
                .build());

        TextField<Article> empty = TextField.of(TITLE, positioned(List.of()));
        assertMissing(snapshot, SearchQueries.<Article>bool()
                .must(SearchQueries.fuzzy(empty, "empty"))
                .should(SearchQueries.fuzzy(competing, "restaurant"))
                .build());
    }

    @Test
    void analyzesAndExpandsEveryReusedOccurrenceExactlyOnce() {
        AtomicInteger analysisCalls = new AtomicInteger();
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                if (text.equals("query")) {
                    analysisCalls.incrementAndGet();
                    return List.of(new AnalyzedToken("restaurant", 1));
                }
                return Analyzer.simple().analyzeWithPositions(text);
            }
        };
        TextField<Article> field = TextField.of(BODY, analyzer);
        SearchSnapshot<Article> snapshot = new SearchSnapshot<Article>(
                List.of(IndexDefinition.text(field)))
                .add(0, new Article(0, "", "restarant", "guide"));
        analysisCalls.set(0);
        AtomicInteger expansionCalls = new AtomicInteger();
        FuzzyTermExpander delegate = new VocabularyScanningFuzzyTermExpander();
        FuzzyTermExpander counting = (index, term, maxEdits) -> {
            expansionCalls.incrementAndGet();
            return delegate.expand(index, term, maxEdits);
        };
        SearchQuery<Article> reused = SearchQueries.fuzzy(field, "query");
        SearchRequest<Article> request = request(SearchQueries.<Article>bool()
                .should(reused)
                .should(reused)
                .build());

        RankedSearchInput<Article> input = RankedSearchInput.from(snapshot, request);
        SearchPlan<Article> plan = new SearchPlanner<Article>(
                new CandidatePlanner<>(),
                counting
        ).plan(input);

        assertEquals(2, analysisCalls.get());
        assertEquals(2, expansionCalls.get());
        assertEquals(1, new SearchExecutor<Article>().execute(plan).size());
    }

    @Test
    void keepsMatchedZeroScoresChecksOverflowAndOrdersEqualScoresById() {
        Article later = new Article(8, "", "restarant", "guide");
        Article earlier = new Article(2, "", "restarant", "guide");
        SearchSnapshot<Article> snapshot = snapshot(later, earlier);
        SearchQuery<Article> base = SearchQueries.fuzzy(BODY_TEXT, "restaurant");

        SearchQuery<Article> underflowed = base
                .boost(Double.MIN_VALUE)
                .boost(Double.MAX_VALUE);
        List<SearchHit<Article>> zeroHits = execute(snapshot, underflowed);
        assertEquals(List.of(earlier, later), documents(zeroHits));
        assertEquals(List.of(0.0, 0.0), zeroHits.stream()
                .map(SearchHit::score)
                .toList());

        SearchQuery<Article> overflow = base
                .boost(Double.MAX_VALUE)
                .boost(8.0);
        assertThrows(ArithmeticException.class, () -> execute(snapshot, overflow));
    }

    @Test
    void keepsAnUnderflowedExactBm25AsAMatchedCanonicalZero() {
        SearchSnapshot<Article> snapshot = snapshot(
                new Article(0, "", "restaurant", "guide")
        );
        RankedSearchInput<Article> input = RankedSearchInput.from(
                snapshot,
                request(SearchQueries.fuzzy(BODY_TEXT, "restaurant"))
        );
        @SuppressWarnings("unchecked")
        NormalizedFuzzyNode<Article> normalized =
                (NormalizedFuzzyNode<Article>) input.root();
        TextIndexSnapshot<Article> textIndex = normalized.textIndex();
        var posting = textIndex.posting("restaurant");
        Bm25Config config = new Bm25Config(1.0, 1.0);
        FuzzyPlan<Article> plan = new FuzzyPlan<>(
                "body",
                textIndex,
                "restaurant",
                List.of(new FuzzyScoringExpansion(
                        "restaurant",
                        new ScoringTerm(
                                "restaurant",
                                posting,
                                Double.MIN_VALUE
                        ),
                        0,
                        1.0
                )),
                posting.documents(),
                config,
                Double.MIN_NORMAL
        );

        FuzzyEvaluation evaluation = plan.evaluateFuzzy(0);
        assertTrue(evaluation.result().matched());
        assertEquals(0.0, evaluation.result().score());
        assertEquals("restaurant", evaluation.selectedTerm());
        ExplanationNode explanation = plan.explain(0);
        assertTrue(explanation.matched());
        assertEquals(0.0, explanation.score());
        assertEquals(0.0, explanation.children().getFirst().score());
    }

    private static void assertInvalidFuzzy(
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
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> execute(
                        new SearchSnapshot<>(List.of()),
                        SearchQueries.fuzzy(TextField.of(BODY, analyzer), "query")
                )
        );
        assertTrue(failure.getMessage().contains("body"));
        assertTrue(failure.getMessage().contains(expectedDetail));
    }

    private static void assertMissing(
            SearchSnapshot<Article> snapshot,
            SearchQuery<Article> query
    ) {
        IllegalStateException failure = assertThrows(
                IllegalStateException.class,
                () -> execute(snapshot, query)
        );
        assertTrue(failure.getMessage().contains("body"));
    }

    private static Analyzer positioned(List<AnalyzedToken> result) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return result;
            }
        };
    }

    private static SearchSnapshot<Article> snapshot(Article... articles) {
        SearchSnapshot<Article> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(TITLE_TEXT),
                IndexDefinition.text(BODY_TEXT),
                IndexDefinition.equality(CATEGORY)
        ));
        for (Article article : articles) {
            snapshot = snapshot.add(article.id(), article);
        }
        return snapshot;
    }

    private static SearchPlan<Article> plan(
            SearchSnapshot<Article> snapshot,
            SearchRequest<Article> request
    ) {
        RankedSearchInput<Article> input = RankedSearchInput.from(snapshot, request);
        return new SearchPlanner<Article>(new CandidatePlanner<>()).plan(input);
    }

    private static SearchRequest<Article> request(SearchQuery<Article> query) {
        return SearchRequest.<Article>builder()
                .query(query)
                .limit(100)
                .build();
    }

    private static SearchRequest<Article> request(
            SearchQuery<Article> query,
            Bm25Config config
    ) {
        return SearchRequest.<Article>builder()
                .query(query)
                .limit(100)
                .bm25(config)
                .build();
    }

    private static SearchRequest<Article> filtered(
            SearchQuery<Article> query,
            Query<Article> filter
    ) {
        return SearchRequest.<Article>builder()
                .query(query)
                .filter(filter)
                .limit(100)
                .build();
    }

    private static List<SearchHit<Article>> execute(
            SearchSnapshot<Article> snapshot,
            SearchQuery<Article> query
    ) {
        return execute(snapshot, request(query));
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

    private static Map<Integer, Double> scoresById(List<SearchHit<Article>> hits) {
        return hits.stream().collect(Collectors.toMap(
                hit -> hit.document().id(),
                SearchHit::score
        ));
    }

    private static double scoreOf(List<SearchHit<Article>> hits, int id) {
        return scoresById(hits).get(id);
    }

    private static List<Integer> ids(List<SearchHit<Article>> hits) {
        return hits.stream().map(hit -> hit.document().id()).toList();
    }

    private static List<Article> documents(List<SearchHit<Article>> hits) {
        return hits.stream().map(SearchHit::document).toList();
    }

    @FunctionalInterface
    private interface PositionedAnalysis {
        List<AnalyzedToken> analyze(String text);
    }

    private record Article(int id, String title, String body, String category) {
    }
}
