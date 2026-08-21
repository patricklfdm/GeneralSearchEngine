package org.example.generalsearch.schema;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.junit.jupiter.api.Test;

class SearchSchemaTest {
    @Test
    void exposesCanonicalProductFieldsAndExtractors() {
        Product product = new Product(
                "p1", "Laptop", Category.ELECTRONICS, 999, true, 4.8);

        assertEquals(Product.class, ProductFields.SCHEMA.documentType());
        assertSame(ProductFields.ID, ProductFields.SCHEMA.idField());
        assertSame(ProductFields.PRICE, ProductFields.SCHEMA.requireField("price"));
        assertEquals(999.0, ProductFields.PRICE.valueOf(product));
        assertEquals(6, ProductFields.SCHEMA.fields().size());
    }

    @Test
    void rejectsMissingIdsAndDuplicateFieldNames() {
        assertThrows(IllegalStateException.class,
                () -> SearchSchema.builder(Product.class)
                        .field(ProductFields.NAME)
                        .build());

        Field<Product, String> duplicateName =
                Field.of("name", String.class, Product::id);
        assertThrows(IllegalArgumentException.class,
                () -> SearchSchema.builder(Product.class)
                        .id(ProductFields.ID)
                        .field(ProductFields.NAME)
                        .field(duplicateName));
    }
}
