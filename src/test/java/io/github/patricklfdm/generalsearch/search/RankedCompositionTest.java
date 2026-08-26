package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;
import java.util.stream.Collectors;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.CandidatePlanner;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class RankedCompositionTest {
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
    void executesMustShouldAndCrossFieldScoresInLogicalOrder() {
        Article both = new Article(0, "java", "search search", "guide");
        Article titleOnly = new Article(1, "java", "other", "guide");
        Article bodyOnly = new Article(2, "other", "search", "reference");
        Article neither = new Article(3, "other", "other", "guide");
        SearchSnapshot<Article> snapshot = snapshot(both, titleOnly, bodyOnly, neither);

        Map<Integer, Double> titleScores = scoresById(execute(
                snapshot,
                SearchQueries.text(TITLE_TEXT, "java")
        ));
        Map<Integer, Double> bodyScores = scoresById(execute(
                snapshot,
                SearchQueries.text(BODY_TEXT, "search")
        ));

        SearchQuery<Article> mustShould = SearchQueries.<Article>bool()
                .must(SearchQueries.text(TITLE_TEXT, "java"))
                .should(SearchQueries.text(BODY_TEXT, "search"))
                .build();
        List<SearchHit<Article>> mustShouldHits = execute(snapshot, mustShould);
        assertEquals(List.of(both, titleOnly), documents(mustShouldHits));
        assertEquals(
                titleScores.get(0) + bodyScores.get(0),
                mustShouldHits.get(0).score()
        );
        assertEquals(titleScores.get(1), mustShouldHits.get(1).score());

        SearchQuery<Article> allShould = SearchQueries.<Article>bool()
                .should(SearchQueries.text(TITLE_TEXT, "java"))
                .should(SearchQueries.text(BODY_TEXT, "search"))
                .build();
        List<SearchHit<Article>> allShouldHits = execute(snapshot, allShould);
        assertEquals(3, allShouldHits.size());
        assertEquals(
                titleScores.get(0) + bodyScores.get(0),
                scoreOf(allShouldHits, 0)
        );
        assertEquals(titleScores.get(1), scoreOf(allShouldHits, 1));
        assertEquals(bodyScores.get(2), scoreOf(allShouldHits, 2));

        SearchQuery<Article> bothMust = SearchQueries.<Article>bool()
                .must(SearchQueries.text(TITLE_TEXT, "java"))
                .must(SearchQueries.text(BODY_TEXT, "search"))
                .build();
        assertEquals(List.of(both), documents(execute(snapshot, bothMust)));
    }

    @Test
    void preservesNestedBoostsAndRepeatedClauseOccurrences() {
        Article article = new Article(0, "java", "search", "guide");
        SearchSnapshot<Article> snapshot = snapshot(article);
        SearchQuery<Article> repeated = SearchQueries.text(TITLE_TEXT, "java");
        double baseScore = execute(snapshot, repeated).getFirst().score();

        SearchQuery<Article> repeatedBool = SearchQueries.<Article>bool()
                .should(repeated)
                .should(repeated)
                .should(repeated.boost(2.0))
                .build();
        assertEquals(
                baseScore + baseScore + baseScore * 2.0,
                execute(snapshot, repeatedBool).getFirst().score()
        );

        SearchQuery<Article> nested = SearchQueries.<Article>bool()
                .must(SearchQueries.<Article>bool()
                        .should(repeated)
                        .should(SearchQueries.text(BODY_TEXT, "search"))
                        .build())
                .should(repeated.boost(3.0))
                .build()
                .boost(2.0);
        double bodyScore = execute(
                snapshot,
                SearchQueries.text(BODY_TEXT, "search")
        ).getFirst().score();
        assertEquals(
                ((baseScore + bodyScore) + baseScore * 3.0) * 2.0,
                execute(snapshot, nested).getFirst().score()
        );
    }

    @Test
    void acceptsTheWholeSupportedTreeAndAnalyzesInLogicalOrder() {
        List<String> analyzed = new ArrayList<>();
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of(new Token(text));
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                analyzed.add(text);
                return List.of();
            }
        };
        TextField<Article> unindexed = TextField.of(TITLE, analyzer);
        SearchQuery<Article> query = SearchQueries.<Article>bool()
                .must(SearchQueries.text(unindexed, "java"))
                .should(SearchQueries.<Article>bool()
                        .must(SearchQueries.text(unindexed, "search"))
                        .should(SearchQueries.fuzzy(unindexed, "jvaa"))
                        .build())
                .build();

        assertTrue(execute(new SearchSnapshot<>(List.of()), query).isEmpty());
        assertEquals(List.of("java", "search", "jvaa"), analyzed);
    }

    @Test
    void analyzesEveryOccurrenceAndRequiresOnlyNonEmptyLeafIndexes() {
        AtomicInteger calls = new AtomicInteger();
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return Analyzer.simple().analyze(text);
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                calls.incrementAndGet();
                return text.equals("empty")
                        ? List.of()
                        : List.of(new AnalyzedToken(text, 1));
            }
        };
        TextField<Article> field = TextField.of(TITLE, analyzer);
        SearchSnapshot<Article> indexed = new SearchSnapshot<Article>(
                List.of(IndexDefinition.text(field)))
                .add(0, new Article(0, "java", "body", "guide"));
        calls.set(0);
        SearchQuery<Article> repeated = SearchQueries.text(field, "java");
        SearchQuery<Article> repeatedTree = SearchQueries.<Article>bool()
                .must(repeated)
                .should(repeated)
                .build();
        assertEquals(1, execute(indexed, repeatedTree).size());
        assertEquals(2, calls.get());

        calls.set(0);
        TextField<Article> missing = TextField.of(BODY, analyzer);
        SearchQuery<Article> allEmpty = SearchQueries.<Article>bool()
                .must(SearchQueries.text(field, "empty"))
                .should(SearchQueries.text(missing, "empty"))
                .build();
        assertTrue(execute(new SearchSnapshot<>(List.of()), allEmpty).isEmpty());
        assertEquals(2, calls.get());

        SearchQuery<Article> boostedEmpty = SearchQueries
                .text(missing, "empty")
                .boost(2.0);
        assertTrue(execute(
                new SearchSnapshot<>(List.of()),
                boostedEmpty
        ).isEmpty());

        SearchQuery<Article> laterMissing = SearchQueries.<Article>bool()
                .must(SearchQueries.text(field, "empty"))
                .should(SearchQueries.text(missing, "required"))
                .build();
        IllegalStateException failure = assertThrows(
                IllegalStateException.class,
                () -> execute(new SearchSnapshot<>(List.of()), laterMissing)
        );
        assertTrue(failure.getMessage().contains("body"));
    }

    @Test
    void validatesMalformedNestedAnalysisInLogicalTraversalOrder() {
        AtomicInteger firstCalls = new AtomicInteger();
        AtomicInteger secondCalls = new AtomicInteger();
        Analyzer first = positioned(text -> {
            firstCalls.incrementAndGet();
            return List.of();
        });
        Analyzer second = positioned(text -> {
            secondCalls.incrementAndGet();
            return List.of(new AnalyzedToken("bad", 0));
        });
        TextField<Article> firstField = TextField.of(TITLE, first);
        TextField<Article> secondField = TextField.of(BODY, second);
        SearchQuery<Article> query = SearchQueries.<Article>bool()
                .must(SearchQueries.text(firstField, "empty"))
                .should(SearchQueries.text(secondField, "bad"))
                .build();

        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> execute(new SearchSnapshot<>(List.of()), query)
        );
        assertTrue(failure.getMessage().contains("body"));
        assertEquals(1, firstCalls.get());
        assertEquals(1, secondCalls.get());
    }

    @Test
    void keepsMatchedZeroScoresAndChecksCompositionOverflow() {
        Article earlier = new Article(0, "java", "body", "guide");
        Article later = new Article(1, "java", "body", "guide");
        SearchSnapshot<Article> snapshot = snapshot(earlier, later);
        SearchQuery<Article> base = SearchQueries.text(TITLE_TEXT, "java");

        SearchQuery<Article> underflowed = base
                .boost(Double.MIN_VALUE)
                .boost(Double.MAX_VALUE);
        List<SearchHit<Article>> zeroHits = execute(snapshot, underflowed);
        assertEquals(List.of(earlier, later), documents(zeroHits));
        assertEquals(List.of(0.0, 0.0), zeroHits.stream()
                .map(SearchHit::score)
                .toList());

        SearchQuery<Article> multiplicationOverflow = base
                .boost(Double.MAX_VALUE)
                .boost(8.0);
        assertThrows(
                ArithmeticException.class,
                () -> execute(snapshot, multiplicationOverflow)
        );

        SearchQuery<Article> enormous = base.boost(Double.MAX_VALUE);
        SearchQuery<Article> additionOverflow = SearchQueries.<Article>bool()
                .should(enormous)
                .should(enormous)
                .should(enormous)
                .should(enormous)
                .should(enormous)
                .should(enormous)
                .build();
        assertThrows(
                ArithmeticException.class,
                () -> execute(snapshot, additionOverflow)
        );
    }

    @Test
    void preservesClauseEncounterOrderForFloatingPointAddition() {
        Article article = new Article(0, "java", "body", "guide");
        SearchSnapshot<Article> snapshot = snapshot(article);
        SearchQuery<Article> base = SearchQueries.text(TITLE_TEXT, "java");
        double baseScore = execute(snapshot, base).getFirst().score();
        SearchQuery<Article> high = base.boost(1.0e16 / baseScore);
        SearchQuery<Article> small = base.boost(1.0 / baseScore);
        double highScore = execute(snapshot, high).getFirst().score();
        double smallScore = execute(snapshot, small).getFirst().score();

        SearchQuery<Article> highFirst = SearchQueries.<Article>bool()
                .should(high)
                .should(small)
                .should(small)
                .should(small)
                .build();
        SearchQuery<Article> smallFirst = SearchQueries.<Article>bool()
                .should(small)
                .should(small)
                .should(small)
                .should(high)
                .build();
        double expectedHighFirst = ((highScore + smallScore) + smallScore)
                + smallScore;
        double expectedSmallFirst = ((smallScore + smallScore) + smallScore)
                + highScore;

        assertNotEquals(expectedHighFirst, expectedSmallFirst);
        assertEquals(
                expectedHighFirst,
                execute(snapshot, highFirst).getFirst().score()
        );
        assertEquals(
                expectedSmallFirst,
                execute(snapshot, smallFirst).getFirst().score()
        );
    }

    @Test
    void appliesStructuredFilterOnlyToEligibility() {
        Article guide = new Article(0, "java", "search", "guide");
        Article reference = new Article(1, "java", "search", "reference");
        SearchSnapshot<Article> snapshot = snapshot(guide, reference);
        SearchQuery<Article> query = SearchQueries.<Article>bool()
                .must(SearchQueries.text(TITLE_TEXT, "java"))
                .should(SearchQueries.text(BODY_TEXT, "search").boost(2.0))
                .build();
        List<SearchHit<Article>> unfiltered = execute(snapshot, query);

        SearchRequest<Article> filtered = SearchRequest.<Article>builder()
                .query(query)
                .filter(Query.eq(CATEGORY, "guide"))
                .build();
        List<SearchHit<Article>> filteredHits = execute(snapshot, filtered);
        assertEquals(List.of(guide), documents(filteredHits));
        assertEquals(scoreOf(unfiltered, 0), filteredHits.getFirst().score());

        AtomicInteger unknownFilterMatches = new AtomicInteger();
        SearchRequest<Article> unknown = SearchRequest.<Article>builder()
                .query(SearchQueries.text(TITLE_TEXT, "unknown"))
                .filter(document -> {
                    unknownFilterMatches.incrementAndGet();
                    return true;
                })
                .build();
        assertTrue(execute(snapshot, unknown).isEmpty());
        assertEquals(0, unknownFilterMatches.get());
    }

    private static Analyzer positioned(
            Function<String, List<AnalyzedToken>> positioned
    ) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return positioned.apply(text);
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

    private static List<SearchHit<Article>> execute(
            SearchSnapshot<Article> snapshot,
            SearchQuery<Article> query
    ) {
        return execute(snapshot, SearchRequest.<Article>builder()
                .query(query)
                .limit(100)
                .build());
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
        return hits.stream()
                .filter(hit -> hit.document().id() == id)
                .findFirst()
                .orElseThrow()
                .score();
    }

    private static List<Article> documents(List<SearchHit<Article>> hits) {
        return hits.stream().map(SearchHit::document).toList();
    }

    private record Article(int id, String title, String body, String category) {
    }
}
