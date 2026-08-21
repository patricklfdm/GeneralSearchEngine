package org.example.generalsearch.filter;

import java.util.Objects;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.query.Query;

/**
 * Temporary bridge for code that still requires the former ProductFilter type.
 */
@Deprecated(forRemoval = false)
@SuppressWarnings("deprecation")
public final class ProductFilterAdapter {
    private ProductFilterAdapter() {}

    public static ProductFilter adapt(Query<Product> query) {
        Objects.requireNonNull(query, "query");
        if (query instanceof ProductFilter productFilter) {
            return productFilter;
        }
        return query::matches;
    }
}
