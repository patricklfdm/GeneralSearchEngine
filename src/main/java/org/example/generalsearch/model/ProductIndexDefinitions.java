package org.example.generalsearch.model;

import java.util.List;
import org.example.generalsearch.index.IndexDefinition;

/**
 * Product default indexes generated from Product annotations.
 */
public final class ProductIndexDefinitions {
    private ProductIndexDefinitions() {}

    public static List<IndexDefinition<Product>> defaults() {
        return ProductFields.indexDefinitions();
    }
}
