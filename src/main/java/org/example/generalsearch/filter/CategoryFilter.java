package org.example.generalsearch.filter;

import java.util.Objects;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;

public record CategoryFilter(Category category) implements ProductFilter {
    public CategoryFilter {
        Objects.requireNonNull(category, "category");
    }

    @Override
    public boolean matches(Product product) {
        return product.category() == category;
    }
}
