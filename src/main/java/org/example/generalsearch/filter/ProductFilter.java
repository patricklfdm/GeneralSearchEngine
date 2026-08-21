package org.example.generalsearch.filter;

import org.example.generalsearch.model.Product;

@FunctionalInterface
public interface ProductFilter {
    boolean matches(Product product);
}
