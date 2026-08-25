package io.github.patricklfdm.generalsearch.schema;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
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

    @Test
    void registersOneCanonicalTextConfigurationPerLogicalField() {
        Field<TextDocument, Long> id = Field.of("id", Long.class, TextDocument::id);
        Field<TextDocument, String> body =
                Field.of("body", String.class, TextDocument::body);
        TextField<TextDocument> text = TextField.of(body, Analyzer.simple());

        SearchSchema<TextDocument, Long> schema =
                SearchSchema.builder(TextDocument.class, id)
                        .textField(text)
                        .build();

        assertSame(body, schema.requireField("body"));
        assertSame(text, schema.requireTextField("body"));
        assertSame(text, schema.textFields().get("body"));
    }

    @Test
    void rejectsCompetingTextConfigurationsForTheSameLogicalField() {
        Field<TextDocument, Long> id = Field.of("id", Long.class, TextDocument::id);
        Field<TextDocument, String> body =
                Field.of("body", String.class, TextDocument::body);
        TextField<TextDocument> first = TextField.of(body, Analyzer.simple());
        TextField<TextDocument> competing = TextField.of(body, Analyzer.simple());

        assertThrows(IllegalArgumentException.class,
                () -> SearchSchema.builder(TextDocument.class, id)
                        .textField(first)
                        .textField(competing));
    }

    @Test
    void lookupFailuresSuggestCloseCanonicalNamesAndListChoices() {
        Field<TextDocument, Long> id = Field.of("id", Long.class, TextDocument::id);
        Field<TextDocument, String> body =
                Field.of("body", String.class, TextDocument::body);
        SearchSchema<TextDocument, Long> schema =
                SearchSchema.builder(TextDocument.class, id)
                        .textField(TextField.of(body, Analyzer.simple()))
                        .build();

        IllegalArgumentException unknownField = assertThrows(
                IllegalArgumentException.class,
                () -> schema.requireField("bod"));
        assertTrue(unknownField.getMessage().contains("Did you mean 'body'?"));
        assertTrue(unknownField.getMessage().contains("Available fields: [id, body]"));

        IllegalArgumentException unknownTextField = assertThrows(
                IllegalArgumentException.class,
                () -> schema.requireTextField("Bodyy"));
        assertTrue(unknownTextField.getMessage().contains("Did you mean 'body'?"));
        assertTrue(unknownTextField.getMessage().contains(
                "Configured text fields: [body]"));
        assertTrue(unknownTextField.getMessage().contains(
                "textIndex(fieldName, analyzer)"));
    }

    private record NullableIdDocument(String id) {}

    private record TextDocument(long id, String body) {}
}
