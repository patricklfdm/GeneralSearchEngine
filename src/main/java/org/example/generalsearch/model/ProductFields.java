package org.example.generalsearch.model;

import org.example.generalsearch.schema.Field;
import org.example.generalsearch.schema.SearchSchema;

/**
 * Canonical, type-safe field definitions for Product queries and schema configuration.
 */
public final class ProductFields {
    public static final Field<Product, String> ID =
            Field.of("id", String.class, Product::id);
    public static final Field<Product, String> NAME =
            Field.of("name", String.class, Product::name);
    public static final Field<Product, Category> CATEGORY =
            Field.of("category", Category.class, Product::category);
    public static final Field<Product, Double> PRICE =
            Field.of("price", Double.class, Product::price);
    public static final Field<Product, Boolean> PRIME =
            Field.of("prime", Boolean.class, Product::prime);
    public static final Field<Product, Double> RATING =
            Field.of("rating", Double.class, Product::rating);

    public static final SearchSchema<Product> SCHEMA =
            SearchSchema.builder(Product.class)
                    .id(ID)
                    .field(NAME)
                    .field(CATEGORY)
                    .field(PRICE)
                    .field(PRIME)
                    .field(RATING)
                    .build();

    private ProductFields() {}
}
