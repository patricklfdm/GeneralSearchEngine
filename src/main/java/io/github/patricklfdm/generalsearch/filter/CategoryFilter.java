package io.github.patricklfdm.generalsearch.filter;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record CategoryFilter(Category category) implements ProductFilter {
    public CategoryFilter {
        Objects.requireNonNull(category, "category");
    }

    @Override
    public boolean matches(Product product) {
        return product.category() == category;
    }
}
