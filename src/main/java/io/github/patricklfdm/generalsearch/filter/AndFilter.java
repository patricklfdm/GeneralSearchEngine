package io.github.patricklfdm.generalsearch.filter;

import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.model.Product;

@SuppressWarnings("deprecation")
public record AndFilter(List<ProductFilter> filters) implements ProductFilter {
    public AndFilter {
        filters = List.copyOf(Objects.requireNonNull(filters, "filters"));
    }

    @Override
    public boolean matches(Product product) {
        return filters.stream().allMatch(filter -> filter.matches(product));
    }
}
