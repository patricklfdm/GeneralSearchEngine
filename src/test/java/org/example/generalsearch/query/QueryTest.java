package org.example.generalsearch.query;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.example.generalsearch.filter.ProductFilter;
import org.example.generalsearch.filter.ProductFilterAdapter;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.junit.jupiter.api.Test;

class QueryTest {
    private static final Product LAPTOP = new Product(
            "p1", "Laptop Pro", Category.ELECTRONICS, 999.0, true, 4.8);

    @Test
    void evaluatesTypedFieldAndCompositeQueries() {
        Query<Product> query = Query.and(
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS),
                Query.between(ProductFields.PRICE, 500.0, 1_500.0),
                Query.prefix(ProductFields.NAME, "Laptop"),
                Query.not(Query.eq(ProductFields.PRIME, false))
        );

        assertTrue(query.matches(LAPTOP));
        assertFalse(Query.eq(ProductFields.CATEGORY, Category.BOOKS).matches(LAPTOP));
        assertTrue(Query.or(
                Query.eq(ProductFields.CATEGORY, Category.BOOKS),
                Query.eq(ProductFields.PRIME, true)
        ).matches(LAPTOP));
        assertTrue(Query.<Product>matchAll().matches(LAPTOP));
    }

    @Test
    void emptyBooleanQueriesHaveConventionalSemantics() {
        assertTrue(Query.<Product>and().matches(LAPTOP));
        assertFalse(Query.<Product>or().matches(LAPTOP));
    }

    @Test
    @SuppressWarnings("deprecation")
    void adaptsANewQueryForFormerProductFilterConsumers() {
        ProductFilter legacy = ProductFilterAdapter.adapt(
                Query.eq(ProductFields.CATEGORY, Category.ELECTRONICS));
        assertTrue(legacy.matches(LAPTOP));
    }
}
