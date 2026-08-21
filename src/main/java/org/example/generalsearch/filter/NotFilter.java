package org.example.generalsearch.filter;

import java.util.Objects;
import org.example.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record NotFilter(ProductFilter filter) implements ProductFilter {
    public NotFilter {
        Objects.requireNonNull(filter, "filter");
    }

    @Override
    public boolean matches(Product product) {
        return !filter.matches(product);
    }
}
