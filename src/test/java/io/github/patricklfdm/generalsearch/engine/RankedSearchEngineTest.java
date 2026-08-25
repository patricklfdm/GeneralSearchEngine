package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class RankedSearchEngineTest {
    private static final Field<Article, Long> ID =
            Field.of("id", Long.class, Article::id);
    private static final Field<Article, String> BODY =
            Field.of("body", String.class, Article::body);
    private static final Field<Article, String> CATEGORY =
            Field.of("category", String.class, Article::category);
    private static final TextField<Article> TEXT =
            TextField.of(BODY, Analyzer.simple());

    @Test
    void rankedCapabilityIsAnAdditiveDefaultInterfaceMethod() throws Exception {
        assertTrue(SearchEngine.class
                .getMethod("searchTopK", RankedSearchRequest.class)
                .isDefault());
    }

    @Test
    void exposesAdditiveRankedCapabilityWithoutChangingUnrankedOrder() {
        Article first = new Article(1, "java", "guide");
        Article second = new Article(2, "java java", "guide");
        Article third = new Article(3, "java search engine", "reference");
        try (SearchEngine<Long, Article> engine = SearchEngine.builder(Article.class, ID)
                .index(IndexDefinition.text(TEXT))
                .index(IndexDefinition.equality(CATEGORY))
                .build()) {
            engine.add(first).join();
            engine.add(second).join();
            engine.add(third).join();
            RankedSearchRequest<Article> request = RankedSearchRequest.filtered(
                    TextScoringQuery.of(TEXT, "java"),
                    Query.eq(CATEGORY, "guide"),
                    10);

            List<Article> insertionOrder = engine.search(Query.term(TEXT, "java"));
            List<SearchHit<Article>> ranked = engine.searchTopK(request);

            assertEquals(List.of(first, second, third), insertionOrder);
            assertEquals(List.of(second, first), documents(ranked));
            assertEquals(insertionOrder, engine.search(Query.term(TEXT, "java")));

            engine.dropIndex("body").join();
            assertThrows(IllegalStateException.class, () -> engine.searchTopK(request));
            engine.createIndex(IndexDefinition.text(TEXT)).join();
            assertEquals(List.of(second, first), documents(engine.searchTopK(request)));
        }
    }

    @Test
    void updateAndRemovePublishRankingMetadataAtomically() {
        Article first = new Article(1, "java", "guide");
        Article second = new Article(2, "java java", "guide");
        try (SearchEngine<Long, Article> engine = SearchEngine.builder(Article.class, ID)
                .index(IndexDefinition.text(TEXT))
                .build()) {
            engine.add(first).join();
            engine.add(second).join();
            RankedSearchRequest<Article> request = RankedSearchRequest.of(
                    TextScoringQuery.of(TEXT, "java"), 10);

            Article updated = new Article(1, "java java java java", "guide");
            engine.update(updated).join();
            engine.remove(2L).join();

            assertEquals(List.of(updated), documents(engine.searchTopK(request)));
        }
    }

    private static List<Article> documents(List<SearchHit<Article>> hits) {
        return hits.stream().map(SearchHit::document).toList();
    }

    private record Article(long id, String body, String category) {}
}
