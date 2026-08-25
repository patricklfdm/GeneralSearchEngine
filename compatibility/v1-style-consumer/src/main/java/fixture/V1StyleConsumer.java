package fixture;

import java.util.List;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

public final class V1StyleConsumer {
    private V1StyleConsumer() {}

    public static List<Item> search() {
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, String> category =
                Field.of("category", String.class, Item::category);
        Field<Item, Integer> price = Field.of("price", Integer.class, Item::price);
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(category)
                .field(price)
                .build();
        try (SearchEngine<Long, Item> engine = SearchEngine.builder(schema)
                .index(IndexDefinition.equality(category))
                .index(IndexDefinition.range(price))
                .build()) {
            engine.add(new Item(1L, "books", 20)).join();
            return engine.search(Query.and(
                    Query.eq(category, "books"),
                    Query.between(price, 10, 30)));
        }
    }

    public record Item(long id, String category, int price) {}
}
