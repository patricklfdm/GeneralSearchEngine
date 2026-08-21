package org.example.generalsearch.schema;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
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
        assertEquals("p1", ProductFields.SCHEMA.idOf(product));
        assertSame(ProductFields.PRICE, ProductFields.SCHEMA.requireField("price"));
        assertEquals(999.0, ProductFields.PRICE.valueOf(product));
        assertEquals(6, ProductFields.SCHEMA.fields().size());
    }

    @Test
    void rejectsNullIdFieldsAndDuplicateFieldNames() {
        assertThrows(NullPointerException.class,
                () -> SearchSchema.builder(Product.class, null));

        Field<Product, String> duplicateName =
                Field.of("name", String.class, Product::id);
        assertThrows(IllegalArgumentException.class,
                () -> SearchSchema.builder(Product.class, ProductFields.ID)
                        .field(ProductFields.NAME)
                        .field(duplicateName));
    }

    @Test
    void rejectsANullExtractedId() {
        Field<NullableIdDocument, String> id =
                Field.of("id", String.class, NullableIdDocument::id);
        SearchSchema<NullableIdDocument, String> schema =
                SearchSchema.builder(NullableIdDocument.class, id).build();

        assertNull(id.valueOf(new NullableIdDocument(null)));
        assertThrows(NullPointerException.class,
                () -> schema.idOf(new NullableIdDocument(null)));
    }

    private record NullableIdDocument(String id) {}
}
