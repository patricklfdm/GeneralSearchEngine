package org.example.generalsearch.filter;

import org.example.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record PrimeFilter(boolean requirePrime) implements ProductFilter {
    @Override
    public boolean matches(Product product) {
        return product.prime() == requirePrime;
    }
}
