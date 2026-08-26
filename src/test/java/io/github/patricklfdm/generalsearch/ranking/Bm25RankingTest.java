package io.github.patricklfdm.generalsearch.ranking;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class Bm25RankingTest {
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());
    private final RankedSearcher<Article> searcher = new RankedSearcher<>();

    @Test
    void matchesHandComputedBm25FormulaAndDeduplicatesQueryTerms() {
        Article first = new Article(0, "java java search", "guide");
        Article second = new Article(1, "java engine", "guide");
        Article third = new Article(2, "search engine engine engine", "reference");
        SearchSnapshot<Article> snapshot = snapshot().add(0, first)
                .add(1, second)
                .add(2, third);

        List<SearchHit<Article>> hits = searcher.search(snapshot, RankedSearchRequest.of(
                TextScoringQuery.of(TEXT, "java search"), 10));
        List<SearchHit<Article>> repeated = searcher.search(
                snapshot,
                RankedSearchRequest.of(
                        TextScoringQuery.of(TEXT, "java java search"), 10));

        assertEquals(List.of(first, second, third), documents(hits));
        assertEquals(1.116258619458622, hits.get(0).score(), 1.0e-12);
        assertEquals(0.544214728600325, hits.get(1).score(), 1.0e-12);
        assertEquals(0.413603193736247, hits.get(2).score(), 1.0e-12);
        assertEquals(scores(hits), scores(repeated));
    }

    @Test
    void appliesBooleanFilterBeforeScoringAndKeepsTopKBounded() {
        Article first = new Article(0, "java java search", "guide");
        Article second = new Article(1, "java engine", "reference");
        Article third = new Article(2, "java", "guide");
        SearchSnapshot<Article> snapshot = snapshot().add(0, first)
                .add(1, second)
                .add(2, third);
        TextScoringQuery<Article> query = TextScoringQuery.of(TEXT, "java");

        List<SearchHit<Article>> one = searcher.search(snapshot,
                RankedSearchRequest.filtered(
                        query, Query.eq(CATEGORY, "guide"), 1));
        List<SearchHit<Article>> oversized = searcher.search(snapshot,
                RankedSearchRequest.filtered(
                        query, Query.eq(CATEGORY, "guide"), 100));

        assertEquals(List.of(third), documents(one));
        assertEquals(List.of(third, first), documents(oversized));
    }

    @Test
    void resolvesEqualScoresByAscendingInternalDocumentId() {
        Article laterDocId = new Article(8, "same term", "guide");
        Article earlierDocId = new Article(2, "same term", "guide");
        SearchSnapshot<Article> snapshot = snapshot()
                .add(8, laterDocId)
                .add(2, earlierDocId);

        List<SearchHit<Article>> hits = searcher.search(snapshot,
                RankedSearchRequest.of(TextScoringQuery.of(TEXT, "same"), 2));

        assertEquals(List.of(earlierDocId, laterDocId), documents(hits));
        assertEquals(hits.get(0).score(), hits.get(1).score());
    }

    @Test
    void mutationMetadataChangesNewRankingWithoutChangingOldSnapshot() {
        Article shortJava = new Article(0, "java", "guide");
        Article repeatedJava = new Article(1, "java java", "guide");
        SearchSnapshot<Article> base = snapshot()
                .add(0, shortJava)
                .add(1, repeatedJava);
        Article updated = new Article(0, "java java java java java", "guide");
        SearchSnapshot<Article> changed = base.update(0, updated).remove(1);
        RankedSearchRequest<Article> request = RankedSearchRequest.of(
                TextScoringQuery.of(TEXT, "java"), 10);

        assertEquals(List.of(repeatedJava, shortJava),
                documents(searcher.search(base, request)));
        assertEquals(List.of(updated), documents(searcher.search(changed, request)));
        assertEquals(List.of(repeatedJava, shortJava),
                documents(searcher.search(base, request)));
    }

    @Test
    void validatesRequestConfigurationAndMissingIndexCases() {
        TextScoringQuery<Article> scoring = TextScoringQuery.of(TEXT, "java");
        assertThrows(IllegalArgumentException.class,
                () -> RankedSearchRequest.of(scoring, 0));
        assertThrows(IllegalArgumentException.class,
                () -> new Bm25Config(-0.1, 0.75));
        assertThrows(IllegalArgumentException.class,
                () -> new Bm25Config(Double.NaN, 0.75));
        assertThrows(IllegalArgumentException.class,
                () -> new Bm25Config(1.2, 1.01));
        assertThrows(NullPointerException.class,
                () -> TextScoringQuery.of(TEXT, null));
        assertThrows(IllegalStateException.class,
                () -> searcher.search(
                        new SearchSnapshot<>(List.of()),
                        RankedSearchRequest.of(scoring, 10)));

        assertTrue(searcher.search(
                new SearchSnapshot<>(List.of()),
                RankedSearchRequest.of(TextScoringQuery.of(TEXT, "---"), 10)
        ).isEmpty());
        assertTrue(searcher.search(
                new SearchSnapshot<>(List.of(IndexDefinition.text(TEXT))),
                RankedSearchRequest.of(scoring, 10)
        ).isEmpty());
    }

    @Test
    void scoringAndIndexingUseNativePositionedAnalysis() {
        Analyzer analyzer = new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return List.of(new Token("legacy"));
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return switch (text) {
                    case "query" -> List.of(new AnalyzedToken("target", 4));
                    case "matching" -> List.of(
                            new AnalyzedToken("target", 2),
                            new AnalyzedToken("synonym", 0));
                    default -> List.of(new AnalyzedToken("other", 1));
                };
            }
        };
        TextField<Article> text = TextField.of(BODY, analyzer);
        Article matching = new Article(1, "matching", "guide");
        Article other = new Article(2, "other", "guide");
        SearchSnapshot<Article> snapshot = new SearchSnapshot<Article>(
                List.of(IndexDefinition.text(text)))
                .add(1, matching)
                .add(2, other);
        TextScoringQuery<Article> scoring = TextScoringQuery.of(text, "query");

        assertEquals(List.of("target"), scoring.terms());
        assertEquals(List.of(matching), documents(searcher.search(
                snapshot, RankedSearchRequest.of(scoring, 10))));
    }

    private static SearchSnapshot<Article> snapshot() {
        return new SearchSnapshot<>(List.of(
                IndexDefinition.text(TEXT),
                IndexDefinition.equality(CATEGORY)));
    }

    private static List<Article> documents(List<SearchHit<Article>> hits) {
        return hits.stream().map(SearchHit::document).toList();
    }

    private static List<Double> scores(List<SearchHit<Article>> hits) {
        return hits.stream().map(SearchHit::score).toList();
    }

    private record Article(int id, String body, String category) {}
}
