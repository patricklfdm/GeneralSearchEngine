package io.github.patricklfdm.generalsearch.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.SnapshotSearcher;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class TextIndexTest {
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void postingsRetainFrequencyAndServeTermAnyAndAllExactly() {
        IndexBuilder<Article> builder = IndexDefinition.text(TEXT)
                .createEmpty()
                .toBuilder();
        builder.add(0, new Article("Java java search"));
        builder.add(1, new Article("Search engine"));
        builder.add(2, new Article(null));
        TextIndexSnapshot<Article> index = textIndex(builder.build());

        assertEquals(new IndexStatistics(2, 3), index.statistics());
        PostingList java = index.posting("java");
        assertEquals(1, java.documentFrequency());
        assertEquals(2, java.termFrequency(0));
        assertEquals(0, java.termFrequency(1));

        assertCandidate(index, Query.term(TEXT, "JAVA"), 1);
        assertCandidate(index, Query.anyTerms(TEXT, "java engine"), 2);
        assertCandidate(index, Query.allTerms(TEXT, "java search"), 1);
        assertCandidate(index, Query.allTerms(TEXT, "java missing"), 0);
        assertCandidate(index, Query.anyTerms(TEXT, "---"), 0);
        assertSame(index, index.toBuilder().build());
    }

    @Test
    void updatesAndRemovalsPreserveOldSnapshots() {
        IndexBuilder<Article> initial = IndexDefinition.text(TEXT)
                .createEmpty()
                .toBuilder();
        initial.add(0, new Article("java search"));
        initial.add(1, new Article("search"));
        TextIndexSnapshot<Article> base = textIndex(initial.build());

        IndexBuilder<Article> changes = base.toBuilder();
        changes.update(0, new Article("java search"), new Article("engine engine"));
        changes.remove(1, new Article("search"));
        TextIndexSnapshot<Article> updated = textIndex(changes.build());

        assertEquals(1, base.posting("java").documentFrequency());
        assertEquals(2, base.posting("search").documentFrequency());
        assertEquals(0, updated.posting("java").documentFrequency());
        assertEquals(0, updated.posting("search").documentFrequency());
        assertEquals(2, updated.posting("engine").termFrequency(0));
        assertEquals(new IndexStatistics(1, 1), updated.statistics());
    }

    @Test
    void estimatesRemainSeparateFromExactCandidateAccuracy() {
        IndexBuilder<Article> builder = IndexDefinition.text(TEXT)
                .createEmpty()
                .toBuilder();
        builder.add(0, new Article("java search"));
        builder.add(1, new Article("java engine"));
        TextIndexSnapshot<Article> index = textIndex(builder.build());

        CandidateEstimate term = index.estimateCandidates(
                Query.term(TEXT, "java")).orElseThrow();
        CandidateEstimate any = index.estimateCandidates(
                Query.anyTerms(TEXT, "search engine")).orElseThrow();
        CandidateEstimate all = index.estimateCandidates(
                Query.allTerms(TEXT, "java search")).orElseThrow();

        assertEquals(EstimateQuality.EXACT, term.quality());
        assertEquals(2, term.estimatedCandidateCardinality());
        assertEquals(EstimateQuality.APPROXIMATE, any.quality());
        assertEquals(CandidateAccuracy.EXACT, any.accuracy());
        assertEquals(EstimateQuality.APPROXIMATE, all.quality());
        assertEquals(CandidateAccuracy.EXACT, all.accuracy());
    }

    @Test
    void keepsMultipleLogicalTextFieldsIndependent() {
        Field<MultiTextArticle, String> title =
                Field.of("title", String.class, MultiTextArticle::title);
        Field<MultiTextArticle, String> body =
                Field.of("body", String.class, MultiTextArticle::body);
        TextField<MultiTextArticle> titleText =
                TextField.of(title, Analyzer.simple());
        TextField<MultiTextArticle> bodyText =
                TextField.of(body, Analyzer.simple());
        SearchSnapshot<MultiTextArticle> snapshot = new SearchSnapshot<>(List.of(
                IndexDefinition.text(titleText),
                IndexDefinition.text(bodyText)))
                .add(0, new MultiTextArticle("Java", "search internals"))
                .add(1, new MultiTextArticle("Search", "java internals"));
        SnapshotSearcher<MultiTextArticle> searcher = new SnapshotSearcher<>();

        assertEquals(List.of(new MultiTextArticle("Java", "search internals")),
                searcher.search(snapshot, Query.term(titleText, "java")));
        assertEquals(List.of(new MultiTextArticle("Search", "java internals")),
                searcher.search(snapshot, Query.term(bodyText, "java")));
    }

    private static void assertCandidate(
            TextIndexSnapshot<Article> index,
            Query<Article> query,
            int expectedCardinality
    ) {
        var result = index.candidates(query).orElseThrow();
        assertEquals(CandidateAccuracy.EXACT, result.accuracy());
        assertEquals(expectedCardinality, result.bitmap().cardinality());
    }

    @SuppressWarnings("unchecked")
    private static TextIndexSnapshot<Article> textIndex(IndexSnapshot<Article> index) {
        assertTrue(index instanceof TextIndexSnapshot<?>);
        return (TextIndexSnapshot<Article>) index;
    }

    private record Article(String body) {}

    private record MultiTextArticle(String title, String body) {}
}
