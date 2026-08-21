package io.github.patricklfdm.generalsearch.model;

import java.util.List;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.schema.AnnotatedSchemaFactory;
import io.github.patricklfdm.generalsearch.schema.AnnotatedSearchConfiguration;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;

/**
 * Canonical, type-safe Product fields generated once from Product annotations.
 */
public final class ProductFields {
    private static final AnnotatedSearchConfiguration<Product, String> CONFIGURATION =
            AnnotatedSchemaFactory.create(Product.class, String.class);

    public static final SearchSchema<Product, String> SCHEMA = CONFIGURATION.schema();
    public static final Field<Product, String> ID =
            SCHEMA.requireField("id", String.class);
    public static final Field<Product, String> NAME =
            SCHEMA.requireField("name", String.class);
    public static final Field<Product, Category> CATEGORY =
            SCHEMA.requireField("category", Category.class);
    public static final Field<Product, Double> PRICE =
            SCHEMA.requireField("price", Double.class);
    public static final Field<Product, Boolean> PRIME =
            SCHEMA.requireField("prime", Boolean.class);
    public static final Field<Product, Double> RATING =
            SCHEMA.requireField("rating", Double.class);

    private ProductFields() {}

    static List<IndexDefinition<Product>> indexDefinitions() {
        return CONFIGURATION.indexDefinitions();
    }
}
