package org.example.generalsearch.filter;

import org.example.generalsearch.model.Product;
import org.example.generalsearch.query.Query;

@FunctionalInterface
@Deprecated(forRemoval = false)
public interface ProductFilter extends Query<Product> {}
