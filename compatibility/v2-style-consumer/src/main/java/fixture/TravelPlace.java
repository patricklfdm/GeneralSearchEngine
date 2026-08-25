package fixture;

import io.github.patricklfdm.generalsearch.schema.annotation.IndexType;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchField;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex;

public record TravelPlace(
        @SearchId long id,
        @SearchIndex(IndexType.EQUALITY) String city,
        @SearchIndex(IndexType.RANGE) double price,
        @SearchField double rating,
        @SearchField String description
) {}
