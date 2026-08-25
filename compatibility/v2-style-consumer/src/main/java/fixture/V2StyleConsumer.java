package fixture;

import java.util.List;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.RankedSearchRequest;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.ranking.TextScoringQuery;
import io.github.patricklfdm.generalsearch.schema.TextField;

public final class V2StyleConsumer {
    private V2StyleConsumer() {}

    public static SearchResult search() {
        try (SearchEngine<Long, TravelPlace> engine =
                     SearchEngine.builder(TravelPlaceSearchFields.SCHEMA)
                             .indexes(TravelPlaceSearchFields.INDEX_DEFINITIONS)
                             .textIndex("description", Analyzer.simple())
                             .build()) {
            TextField<TravelPlace> description =
                    engine.textField("description");
            TravelPlace museum = new TravelPlace(
                    1L, "Paris", 120.0, 4.9, "museum museum riverside");
            TravelPlace guide = new TravelPlace(
                    2L, "Paris", 90.0, 4.4, "museum city guide");
            TravelPlace otherCity = new TravelPlace(
                    3L, "Rome", 80.0, 4.8, "museum museum");
            engine.addAll(List.of(museum, guide, otherCity)).join();

            List<TravelPlace> structured = engine.search(Query.and(
                    Query.eq(TravelPlaceSearchFields.CITY, "Paris"),
                    Query.between(TravelPlaceSearchFields.PRICE, 80.0, 130.0),
                    Query.term(description, "museum")));
            List<SearchHit<TravelPlace>> ranked = engine.searchTopK(
                    RankedSearchRequest.filtered(
                            TextScoringQuery.of(description, "museum"),
                            Query.eq(TravelPlaceSearchFields.CITY, "Paris"),
                            10));

            // RATING is in the generated schema even without a startup index.
            engine.createIndex(IndexDefinition.range(
                    TravelPlaceSearchFields.RATING)).join();
            List<TravelPlace> highlyRated = engine.search(Query.between(
                    TravelPlaceSearchFields.RATING, 4.7, 5.0));
            return new SearchResult(structured, ranked, highlyRated);
        }
    }

    public record SearchResult(
            List<TravelPlace> structured,
            List<SearchHit<TravelPlace>> ranked,
            List<TravelPlace> highlyRated
    ) {}
}
