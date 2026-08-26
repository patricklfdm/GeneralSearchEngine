package fixture;

import java.util.List;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.ranking.SearchHit;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import io.github.patricklfdm.generalsearch.search.ExplanationNode;
import io.github.patricklfdm.generalsearch.search.SearchExplanation;
import io.github.patricklfdm.generalsearch.search.SearchQueries;
import io.github.patricklfdm.generalsearch.search.SearchQuery;
import io.github.patricklfdm.generalsearch.search.SearchRequest;
import io.github.patricklfdm.generalsearch.search.SearchResult;

public final class V3StyleConsumer {
    private static final Field<TravelPlace, Long> ID =
            Field.of("id", Long.class, TravelPlace::id);
    private static final Field<TravelPlace, String> CITY =
            Field.of("city", String.class, TravelPlace::city);
    private static final Field<TravelPlace, String> DESCRIPTION =
            Field.of("description", String.class, TravelPlace::description);
    private static final TextField<TravelPlace> DESCRIPTION_TEXT =
            TextField.of(DESCRIPTION, Analyzer.simple());

    private V3StyleConsumer() {
    }

    public static SearchRequest<TravelPlace> request() {
        SearchQuery<TravelPlace> query = SearchQueries.<TravelPlace>bool()
                .must(SearchQueries.text(DESCRIPTION_TEXT, "historic temple"))
                .should(SearchQueries.phrase(
                        DESCRIPTION_TEXT, "quiet neighborhood").boost(2.0))
                .should(SearchQueries.fuzzy(DESCRIPTION_TEXT, "restarant"))
                .build();

        return SearchRequest.<TravelPlace>builder()
                .query(query)
                .filter(Query.eq(CITY, "Tokyo"))
                .limit(10)
                .build();
    }

    public static SearchRequest<TravelPlace> defaultRequest() {
        return SearchRequest.of(SearchQueries.text(DESCRIPTION_TEXT, "museum"));
    }

    public static List<AnalyzedToken> positionAwareAnalysis() {
        Analyzer legacy = text -> List.of(new Token(text));
        List<AnalyzedToken> adapted = legacy.analyzeWithPositions("museum");
        return List.of(adapted.getFirst(), new AnalyzedToken("gallery", 0));
    }

    public static SearchResult<TravelPlace> search(
            SearchEngine<Long, TravelPlace> engine
    ) {
        return engine.search(request());
    }

    public static SearchResult<TravelPlace> supportedTextSearch(
            SearchEngine<Long, TravelPlace> engine
    ) {
        return engine.search(defaultRequest());
    }

    public static SearchResult<TravelPlace> supportedTextSearch() {
        TravelPlace museum = new TravelPlace(
                1L,
                "Paris",
                "museum museum riverside"
        );
        TravelPlace guide = new TravelPlace(
                2L,
                "Paris",
                "museum city guide"
        );
        TravelPlace other = new TravelPlace(
                3L,
                "Rome",
                "historic temple"
        );
        try (SearchEngine<Long, TravelPlace> engine = SearchEngine
                .builder(TravelPlace.class, ID)
                .index(IndexDefinition.text(DESCRIPTION_TEXT))
                .build()) {
            engine.addAll(List.of(museum, guide, other)).join();
            return supportedTextSearch(engine);
        }
    }

    public static Optional<SearchExplanation<TravelPlace>> explain(
            SearchEngine<Long, TravelPlace> engine,
            long id
    ) {
        return engine.explain(request(), id);
    }

    public static SearchResult<TravelPlace> externalResult(TravelPlace place) {
        return new SearchResult<>(List.of(new SearchHit<>(place, 1.0)));
    }

    public static SearchExplanation<TravelPlace> externalExplanation(
            TravelPlace place
    ) {
        ExplanationNode detail =
                new ExplanationNode(true, 1.0, "fixture", List.of());
        return new SearchExplanation<>(place, true, 1.0, detail);
    }
}
