package io.github.patricklfdm.generalsearch.filter;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.model.Product;

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
