package io.github.patricklfdm.generalsearch.filter;

import io.github.patricklfdm.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record RatingFilter(double minRating, double maxRating) implements ProductFilter {
    public RatingFilter(double minRating) {
        this(minRating, Double.MAX_VALUE);
    }

    @Override
    public boolean matches(Product product) {
        return product.rating() >= minRating && product.rating() <= maxRating;
    }
}
