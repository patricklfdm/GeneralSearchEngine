package org.example.generalsearch.filter;

import org.example.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record PriceRangeFilter(double minPrice, double maxPrice) implements ProductFilter {
    @Override
    public boolean matches(Product product) {
        return product.price() >= minPrice && product.price() <= maxPrice;
    }
}
