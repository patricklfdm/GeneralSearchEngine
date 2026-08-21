package org.example.generalsearch.model;

import java.util.List;
import org.example.generalsearch.index.IndexDefinition;

/**
 * Product-specific index assembly used until engine construction becomes schema-driven.
 */
public final class ProductIndexDefinitions {
    private ProductIndexDefinitions() {}

    public static List<IndexDefinition<Product>> defaults() {
        return List.of(
                IndexDefinition.<Product, Category>equality(ProductFields.CATEGORY),
                IndexDefinition.<Product, Boolean>equality(ProductFields.PRIME),
                IndexDefinition.<Product, Double>range(ProductFields.PRICE)
        );
    }
}
