package example.travel;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.schema.annotation.IndexType;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;

/** Processor-free travel search example for the current development API. */
public final class TravelSearchDemo {
    private TravelSearchDemo() {}

    public static void main(String[] args) {
        try (SearchEngine<Long, TravelPlace> engine = SearchEngine
                .annotatedBuilder(TravelPlace.class, Long.class)
                .textIndex("city", Analyzer.simple())
                .textIndex("description", Analyzer.simple())
                .build()) {
            Field<TravelPlace, String> city = engine.field("city", String.class);
            Field<TravelPlace, Double> price = engine.field("price", Double.class);
            Field<TravelPlace, Double> rating = engine.field("rating", Double.class);
            TextField<TravelPlace> cityText = engine.textField("city");
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

            SearchRequest<TravelPlace> rankedRequest = SearchRequest
                    .<TravelPlace>builder()
                    .query(SearchQueries.text(description, "museum river art"))
                    .filter(Query.eq(city, "Paris"))
                    .limit(3)
                    .build();
            printHits("V3 ranked TEXT + filter", engine.search(rankedRequest));

            SearchRequest<TravelPlace> discoveryRequest = SearchRequest.of(
                    SearchQueries.<TravelPlace>bool()
                            .must(SearchQueries.text(description, "museum"))
                            .should(SearchQueries.text(cityText, "Paris").boost(1.5))
                            .should(SearchQueries.phrase(
                                    description,
                                    "museum beside the river"
                            ).boost(2.0))
                            .build()
            );
            printHits("Cross-field BOOL + BOOST", engine.search(discoveryRequest));

            printHits("Exact PHRASE", engine.search(SearchRequest.of(
                    SearchQueries.phrase(description, "museum beside the river")
            )));
            printHits("FUZZY typo", engine.search(SearchRequest.of(
                    SearchQueries.fuzzy(description, "musuem")
            )));

            engine.explain(discoveryRequest, 1L).ifPresent(explanation ->
                    System.out.printf(
                            "Explain id=1: matched=%s score=%.4f root=%s%n",
                            explanation.matched(),
                            explanation.score(),
                            explanation.detail().description()
                    ));

            engine.createIndex(IndexDefinition.range(rating)).join();
            List<TravelPlace> highlyRated = engine.search(
                    Query.between(rating, 4.7, 5.0));
            System.out.println("Dynamic rating index: " + highlyRated);
            engine.dropIndex("rating").join();
            System.out.println("After dynamic index drop (scan fallback): "
                    + engine.search(Query.between(rating, 4.7, 5.0)));
            System.out.println("Metrics: " + engine.metrics());
        }
    }

    private static void printHits(
            String label,
            SearchResult<TravelPlace> result
    ) {
        System.out.println(label + ":");
        result.hits().forEach(hit -> System.out.printf(
                "  score=%.4f  %s%n",
                hit.score(),
                hit.document()
        ));
    }

    record TravelPlace(
            @SearchId long id,
            @SearchIndex(IndexType.EQUALITY) String city,
            @SearchIndex(IndexType.RANGE) double price,
            double rating,
            String description
    ) {}
}
