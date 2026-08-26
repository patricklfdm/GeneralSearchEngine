package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Function;
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

class PhraseSearchTest {
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
    void matchesOnlyExactRelativeSequencesAndUsesTextBm25() {
        Article exact = new Article(0, "title", "new york city", "guide");
        Article separated = new Article(
                1,
                "title",
                "new amazing york city",
                "guide"
        );
        Article reversed = new Article(2, "title", "york new city", "guide");
        Article exactShort = new Article(3, "title", "new york", "guide");
        SearchSnapshot<Article> snapshot = snapshot(
                TITLE_TEXT,
                BODY_TEXT,
                exact,
                separated,
                reversed,
                exactShort
        );

        List<SearchHit<Article>> phrase = execute(
                snapshot,
                SearchQueries.phrase(BODY_TEXT, "new york")
        );
        Map<Integer, Double> textScores = scoresById(execute(
                snapshot,
                SearchQueries.text(BODY_TEXT, "new york")
        ));

        assertEquals(List.of(exactShort, exact), documents(phrase));
        assertEquals(textScores.get(3), phrase.get(0).score());
        assertEquals(textScores.get(0), phrase.get(1).score());
        assertTrue(execute(
                snapshot,
                SearchQueries.phrase(BODY_TEXT, "unknown york")
        ).isEmpty());
    }

    @Test
    void preservesRepeatedTermsForMatchingButDeduplicatesScoring() {
        Article matching = new Article(0, "title", "very very good", "guide");
        Article extra = new Article(1, "title", "very very very good", "guide");
        Article insufficient = new Article(2, "title", "very good", "guide");
        Article separated = new Article(3, "title", "very good very", "guide");
        SearchSnapshot<Article> snapshot = snapshot(
                TITLE_TEXT,
                BODY_TEXT,
                matching,
                extra,
                insufficient,
                separated
        );

        List<SearchHit<Article>> phrase = execute(
                snapshot,
                SearchQueries.phrase(BODY_TEXT, "very very good")
        );
        Map<Integer, Double> textScores = scoresById(execute(
                snapshot,
                SearchQueries.text(BODY_TEXT, "very very good")
        ));

        assertEquals(List.of(matching, extra), documents(phrase));
        assertEquals(textScores.get(0), scoreOf(phrase, 0));
        assertEquals(textScores.get(1), scoreOf(phrase, 1));
    }

    @Test
    void preservesInitialAndInternalGapsAndSamePositionAlternatives() {
        Analyzer analyzer = positioned(text -> switch (text) {
            case "gap-query" -> List.of(
                    new AnalyzedToken("quick", 5),
                    new AnalyzedToken("brown", 2)
            );
            case "gap-document" -> List.of(
                    new AnalyzedToken("quick", 1),
                    new AnalyzedToken("brown", 2)
            );
            case "adjacent-document" -> List.of(
                    new AnalyzedToken("quick", 1),
                    new AnalyzedToken("brown", 1)
            );
            case "alternative-query" -> List.of(
                    new AnalyzedToken("usa", 4),
                    new AnalyzedToken("united_states", 0),
                    new AnalyzedToken("travel", 1)
            );
            case "usa-document" -> List.of(
                    new AnalyzedToken("usa", 1),
                    new AnalyzedToken("travel", 1)
            );
            case "united-document" -> List.of(
                    new AnalyzedToken("united_states", 1),
                    new AnalyzedToken("travel", 1)
            );
            case "both-document" -> List.of(
                    new AnalyzedToken("usa", 1),
                    new AnalyzedToken("united_states", 0),
                    new AnalyzedToken("travel", 1)
            );
            case "wrong-alternative-document" -> List.of(
                    new AnalyzedToken("america", 1),
                    new AnalyzedToken("travel", 1)
            );
            default -> List.of();
        });
        TextField<Article> field = TextField.of(BODY, analyzer);
        Article gap = new Article(0, "title", "gap-document", "guide");
        Article adjacent = new Article(1, "title", "adjacent-document", "guide");
        Article usa = new Article(2, "title", "usa-document", "guide");
        Article united = new Article(3, "title", "united-document", "guide");
        Article both = new Article(4, "title", "both-document", "guide");
        Article wrong = new Article(
                5,
                "title",
                "wrong-alternative-document",
                "guide"
        );
        SearchSnapshot<Article> snapshot = snapshot(
                TITLE_TEXT,
                field,
                gap,
                adjacent,
                usa,
                united,
                both,
                wrong
        );

        assertEquals(
                List.of(gap),
                documents(execute(
                        snapshot,
                        SearchQueries.phrase(field, "gap-query")
                ))
        );

        List<SearchHit<Article>> alternatives = execute(
                snapshot,
                SearchQueries.phrase(field, "alternative-query")
        );
        Map<Integer, Double> textScores = scoresById(execute(
                snapshot,
                SearchQueries.text(field, "alternative-query")
        ));
        assertEquals(List.of(both, usa, united), documents(alternatives));
        assertEquals(textScores.get(2), scoreOf(alternatives, 2));
        assertEquals(textScores.get(3), scoreOf(alternatives, 3));
        assertEquals(textScores.get(4), scoreOf(alternatives, 4));
        assertTrue(scoreOf(alternatives, 4) > scoreOf(alternatives, 2));
        assertTrue(scoreOf(alternatives, 4) > scoreOf(alternatives, 3));
    }

    @Test
    void composesWithBoolBoostCrossFieldAndStructuredFilters() {
        Article both = new Article(0, "java", "search engine", "guide");
        Article textOnly = new Article(1, "java", "engine search", "guide");
        Article filtered = new Article(2, "java", "search engine", "reference");
        SearchSnapshot<Article> snapshot = snapshot(
                TITLE_TEXT,
                BODY_TEXT,
                both,
                textOnly,
                filtered
        );
        double titleScore = scoreOf(execute(
                snapshot,
                SearchQueries.text(TITLE_TEXT, "java")
        ), 0);
        double phraseScore = scoreOf(execute(
                snapshot,
                SearchQueries.phrase(BODY_TEXT, "search engine")
        ), 0);
        SearchQuery<Article> query = SearchQueries.<Article>bool()
                .must(SearchQueries.text(TITLE_TEXT, "java"))
                .should(SearchQueries.phrase(
                        BODY_TEXT,
                        "search engine"
                ).boost(2.0))
                .build();

        List<SearchHit<Article>> unfiltered = execute(snapshot, query);
        assertEquals(titleScore + phraseScore * 2.0, scoreOf(unfiltered, 0));
        assertEquals(titleScore, scoreOf(unfiltered, 1));

        SearchRequest<Article> request = SearchRequest.<Article>builder()
                .query(query)
                .filter(Query.eq(CATEGORY, "guide"))
                .limit(100)
                .build();
        List<SearchHit<Article>> guideOnly = execute(snapshot, request);
        assertEquals(List.of(both, textOnly), documents(guideOnly));
        assertEquals(scoreOf(unfiltered, 0), scoreOf(guideOnly, 0));
    }

    @Test
    void retainsMatchedZeroScoresAndChecksPhraseCompositionArithmetic() {
        Article earlier = new Article(0, "title", "java search", "guide");
        Article later = new Article(1, "title", "java search", "guide");
        SearchSnapshot<Article> snapshot = snapshot(
                TITLE_TEXT,
                BODY_TEXT,
                earlier,
                later
        );
        SearchQuery<Article> phrase = SearchQueries.phrase(
                BODY_TEXT,
                "java search"
        );

        List<SearchHit<Article>> zero = execute(
                snapshot,
                phrase.boost(Double.MIN_VALUE).boost(Double.MAX_VALUE)
        );
        assertEquals(List.of(earlier, later), documents(zero));
        assertEquals(List.of(0.0, 0.0), zero.stream()
                .map(SearchHit::score)
                .toList());

        assertThrows(
                ArithmeticException.class,
                () -> execute(
                        snapshot,
                        phrase.boost(Double.MAX_VALUE).boost(8.0)
                )
        );

        SearchQuery<Article> enormous = phrase.boost(Double.MAX_VALUE);
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
    void preservesEmptyAndMissingIndexPrecedence() {
        AtomicInteger calls = new AtomicInteger();
        Analyzer analyzer = positioned(text -> {
            calls.incrementAndGet();
            return text.equals("empty")
                    ? List.of()
                    : List.of(new AnalyzedToken(text, 1));
        });
        TextField<Article> indexed = TextField.of(TITLE, analyzer);
        TextField<Article> missing = TextField.of(BODY, analyzer);

        SearchQuery<Article> allEmpty = SearchQueries.<Article>bool()
                .must(SearchQueries.phrase(indexed, "empty"))
                .should(SearchQueries.phrase(missing, "empty"))
                .build();
        assertTrue(execute(new SearchSnapshot<>(List.of()), allEmpty).isEmpty());
        assertEquals(2, calls.get());

        SearchQuery<Article> laterMissing = SearchQueries.<Article>bool()
                .must(SearchQueries.phrase(indexed, "empty"))
                .should(SearchQueries.phrase(missing, "required"))
                .build();
        IllegalStateException missingFailure = assertThrows(
                IllegalStateException.class,
                () -> execute(new SearchSnapshot<>(List.of()), laterMissing)
        );
        assertTrue(missingFailure.getMessage().contains("body"));

    }

    @Test
    void validatesEachOccurrenceAndSelectsTheSmallestUnionedSlot() {
        AtomicInteger calls = new AtomicInteger();
        Analyzer analyzer = positioned(text -> {
            calls.incrementAndGet();
            return Analyzer.simple().analyze(text).stream()
                    .map(token -> new AnalyzedToken(token.term(), 1))
                    .toList();
        });
        TextField<Article> field = TextField.of(BODY, analyzer);
        Article exact = new Article(0, "title", "common rare", "guide");
        Article reversed = new Article(1, "title", "rare common", "guide");
        Article common = new Article(2, "title", "common only", "guide");
        SearchSnapshot<Article> snapshot = snapshot(
                TITLE_TEXT,
                field,
                exact,
                reversed,
                common
        );
        calls.set(0);
        SearchQuery<Article> phrase = SearchQueries.phrase(field, "common rare");
        SearchQuery<Article> repeated = SearchQueries.<Article>bool()
                .should(phrase)
                .should(phrase)
                .build();

        RankedSearchInput<Article> input = RankedSearchInput.from(
                snapshot,
                SearchRequest.<Article>builder()
                        .query(repeated)
                        .limit(100)
                        .build()
        );
        SearchPlan<Article> plan = new SearchPlanner<Article>(new CandidatePlanner<>())
                .plan(input);
        BoolPlan<?> root = assertInstanceOf(BoolPlan.class, plan.root());
        PhrasePlan<?> first = assertInstanceOf(
                PhrasePlan.class,
                root.should().getFirst()
        );

        assertEquals(2, calls.get());
        assertEquals(1, first.anchorSlot());
        assertEquals(2, first.candidates().cardinality());
        assertEquals(List.of(exact), documents(new SearchExecutor<Article>()
                .execute(plan)));
    }

    @Test
    void rejectsMalformedPhraseAnalysisWithoutPartialPlanning() {
        Analyzer malformed = positioned(text -> switch (text) {
            case "null" -> null;
            case "element" -> Arrays.asList((AnalyzedToken) null);
            case "first" -> List.of(new AnalyzedToken("term", 0));
            default -> List.of(
                    new AnalyzedToken("first", Integer.MAX_VALUE),
                    new AnalyzedToken("second", 2)
            );
        });
        TextField<Article> field = TextField.of(BODY, malformed);

        assertInvalid(field, "null", "null token list");
        assertInvalid(field, "element", "null token at index 0");
        assertInvalid(field, "first", "non-positive first position increment");
        assertInvalid(field, "overflow", "overflowed logical position");
    }

    @Test
    void keepsOldSnapshotPhraseTruthAfterTokenReorder() {
        Article original = new Article(0, "title", "java search engine", "guide");
        Article reordered = new Article(0, "title", "search java engine", "guide");
        SearchSnapshot<Article> oldSnapshot = snapshot(
                TITLE_TEXT,
                BODY_TEXT,
                original
        );
        SearchSnapshot<Article> newSnapshot = oldSnapshot.update(0, reordered);
        SearchQuery<Article> phrase = SearchQueries.phrase(BODY_TEXT, "java search");

        assertEquals(List.of(original), documents(execute(oldSnapshot, phrase)));
        assertTrue(execute(newSnapshot, phrase).isEmpty());
        assertEquals(List.of(original), documents(execute(oldSnapshot, phrase)));
        assertFalse(execute(
                newSnapshot,
                SearchQueries.phrase(BODY_TEXT, "search java")
        ).isEmpty());
    }

    private static void assertInvalid(
            TextField<Article> field,
            String text,
            String message
    ) {
        IllegalArgumentException failure = assertThrows(
                IllegalArgumentException.class,
                () -> execute(
                        new SearchSnapshot<>(List.of()),
                        SearchQueries.phrase(field, text)
                )
        );
        assertTrue(failure.getMessage().contains(message));
    }

    private static Analyzer positioned(
            Function<String, List<AnalyzedToken>> positioned
    ) {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                List<AnalyzedToken> tokens = positioned.apply(text);
                return tokens == null
                        ? null
                        : tokens.stream().map(token ->
                                token == null ? null : new Token(token.term())).toList();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return positioned.apply(text);
            }
        };
    }

    private static SearchSnapshot<Article> snapshot(
            TextField<Article> title,
            TextField<Article> body,
            Article... articles
    ) {
        SearchSnapshot<Article> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(title),
                IndexDefinition.text(body),
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
        Map<Integer, Double> scores = new HashMap<>();
        for (SearchHit<Article> hit : hits) {
            scores.put(hit.document().id(), hit.score());
        }
        return Map.copyOf(scores);
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
