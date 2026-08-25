package io.github.patricklfdm.generalsearch.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
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
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
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

    @Test
    void existingSchemaCanAddTextAndLaterIndexAnUnindexedField() {
        Field<TravelPlace, Long> id = Field.of("id", Long.class, TravelPlace::id);
        Field<TravelPlace, String> city =
                Field.of("city", String.class, TravelPlace::city);
        Field<TravelPlace, Double> price =
                Field.of("price", Double.class, TravelPlace::price);
        Field<TravelPlace, Double> rating =
                Field.of("rating", Double.class, TravelPlace::rating);
        Field<TravelPlace, String> description =
                Field.of("description", String.class, TravelPlace::description);
        SearchSchema<TravelPlace, Long> generatedStyleSchema =
                SearchSchema.builder(TravelPlace.class, id)
                        .field(city)
                        .field(price)
                        .field(rating)
                        .field(description)
                        .build();
        TextField<TravelPlace> text = TextField.of(description, Analyzer.simple());

        TravelPlace first = new TravelPlace(
                1, "Paris", 120.0, 4.9, "museum museum museum");
        TravelPlace second = new TravelPlace(
                2, "Paris", 90.0, 4.4, "museum guide");
        TravelPlace third = new TravelPlace(
                3, "Rome", 80.0, 4.8, "museum museum");

        try (SearchEngine<Long, TravelPlace> engine =
                     SearchEngine.builder(generatedStyleSchema)
                             .indexes(List.of(
                                     IndexDefinition.equality(city),
                                     IndexDefinition.range(price)))
                             .index(IndexDefinition.text(text))
                             .build()) {
            assertTrue(generatedStyleSchema.textFields().isEmpty());
            assertSame(text, engine.schema().requireTextField("description"));
            engine.addAll(List.of(first, second, third)).join();

            assertEquals(List.of(first, second), engine.search(Query.and(
                    Query.eq(city, "Paris"),
                    Query.between(price, 80.0, 130.0),
                    Query.term(text, "museum"))));

            List<SearchHit<TravelPlace>> ranked = engine.searchTopK(
                    RankedSearchRequest.filtered(
                            TextScoringQuery.of(text, "museum"),
                            Query.eq(city, "Paris"),
                            10));
            assertEquals(List.of(first, second), documents(ranked));

            engine.createIndex(IndexDefinition.range(rating)).join();
            assertEquals(List.of(first, third), engine.search(
                    Query.between(rating, 4.7, 5.0)));
            assertEquals(4, engine.metrics().registeredIndexCount());
        }
    }

    private static <T> List<T> documents(List<SearchHit<T>> hits) {
        return hits.stream().map(SearchHit::document).toList();
    }

    private record Article(long id, String body, String category) {}

    private record TravelPlace(
            long id,
            String city,
            double price,
            double rating,
            String description
    ) {}
}
