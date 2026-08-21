package org.example.generalsearch.filter;

import java.util.Objects;
import org.example.generalsearch.model.Product;

public record NameFilter(String prefix) implements ProductFilter {
    public NameFilter {
        Objects.requireNonNull(prefix, "prefix");
    }

    @Override
    public boolean matches(Product product) {
        return product.name().startsWith(prefix);
    }
}
