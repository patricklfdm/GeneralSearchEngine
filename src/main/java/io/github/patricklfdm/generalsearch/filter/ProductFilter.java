package io.github.patricklfdm.generalsearch.filter;

import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.query.Query;

@FunctionalInterface
@Deprecated(forRemoval = false)
public interface ProductFilter extends Query<Product> {}
