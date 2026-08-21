package io.github.patricklfdm.generalsearch.filter;

import io.github.patricklfdm.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record PrimeFilter(boolean requirePrime) implements ProductFilter {
    @Override
    public boolean matches(Product product) {
        return product.prime() == requirePrime;
    }
}
