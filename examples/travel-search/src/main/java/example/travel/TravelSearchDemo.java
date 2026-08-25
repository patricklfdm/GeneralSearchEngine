package example.travel;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.schema.annotation.IndexType;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex;

/** Processor-free travel search example for the current development API. */
public final class TravelSearchDemo {
    private TravelSearchDemo() {}

    public static void main(String[] args) {
        try (SearchEngine<Long, TravelPlace> engine = SearchEngine
                .annotatedBuilder(TravelPlace.class, Long.class)
                .textIndex("description", Analyzer.simple())
                .build()) {
            Field<TravelPlace, String> city = engine.field("city", String.class);
            Field<TravelPlace, Double> price = engine.field("price", Double.class);
            Field<TravelPlace, Double> rating = engine.field("rating", Double.class);
            TextField<TravelPlace> description = engine.textField("description");

            engine.addAll(List.of(
                    new TravelPlace(
                            1L,
                            "Paris",
                            120.0,
                            4.9,
                            "Quiet museum beside the river with modern art"),
                    new TravelPlace(
                            2L,
                            "Paris",
                            85.0,
                            4.5,
                            "Popular museum and city walking guide"),
                    new TravelPlace(
                            3L,
                            "Rome",
                            95.0,
                            4.8,
                            "Historic art museum near the old city"),
                    new TravelPlace(
                            4L,
                            "Paris",
                            210.0,
                            4.7,
                            "Luxury hotel overlooking the river")
            )).join();

            List<TravelPlace> parisMuseums = engine.search(Query.and(
                    Query.eq(city, "Paris"),
                    Query.between(price, 80.0, 150.0),
                    Query.term(description, "museum")
            ));
            System.out.println("Structured + text: " + parisMuseums);

            List<SearchHit<TravelPlace>> ranked = engine.searchTopK(
                    RankedSearchRequest.filtered(
                            TextScoringQuery.of(description, "museum river art"),
                            Query.eq(city, "Paris"),
                            3
                    ));
            System.out.println("Filtered BM25:");
            ranked.forEach(hit -> System.out.printf(
                    "  score=%.4f  %s%n",
                    hit.score(),
                    hit.document()
            ));

            engine.createIndex(IndexDefinition.range(rating)).join();
            List<TravelPlace> highlyRated = engine.search(
                    Query.between(rating, 4.7, 5.0));
            System.out.println("Dynamic rating index: " + highlyRated);
            System.out.println("Metrics: " + engine.metrics());
        }
    }

    record TravelPlace(
            @SearchId long id,
            @SearchIndex(IndexType.EQUALITY) String city,
            @SearchIndex(IndexType.RANGE) double price,
            double rating,
            String description
    ) {}
}
