package io.github.patricklfdm.generalsearch.filter;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record NameFilter(String prefix) implements ProductFilter {
    public NameFilter {
        Objects.requireNonNull(prefix, "prefix");
    }

    @Override
    public boolean matches(Product product) {
        return product.name().startsWith(prefix);
    }
}
