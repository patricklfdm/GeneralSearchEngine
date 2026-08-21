package org.example.generalsearch.filter;

import java.util.Objects;
import org.example.generalsearch.model.ProductFields;
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

    public static Query<Product> toQuery(ProductFilter filter) {
        Objects.requireNonNull(filter, "filter");
        if (filter instanceof CategoryFilter category) {
            return Query.eq(ProductFields.CATEGORY, category.category());
        }
        if (filter instanceof PrimeFilter prime) {
            return Query.eq(ProductFields.PRIME, prime.requirePrime());
        }
        if (filter instanceof PriceRangeFilter price) {
            return Query.between(ProductFields.PRICE, price.minPrice(), price.maxPrice());
        }
        if (filter instanceof NameFilter name) {
            return Query.prefix(ProductFields.NAME, name.prefix());
        }
        if (filter instanceof RatingFilter rating) {
            return Query.between(
                    ProductFields.RATING,
                    rating.minRating(),
                    rating.maxRating()
            );
        }
        if (filter instanceof AndFilter and) {
            return Query.and(and.filters().stream()
                    .map(ProductFilterAdapter::toQuery)
                    .toList());
        }
        if (filter instanceof OrFilter or) {
            return Query.or(or.filters().stream()
                    .map(ProductFilterAdapter::toQuery)
                    .toList());
        }
        if (filter instanceof NotFilter not) {
            return Query.not(toQuery(not.filter()));
        }
        return filter;
    }
}
