package org.example.generalsearch.schema;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.example.generalsearch.engine.SearchEngine;
import org.example.generalsearch.engine.SnapshotSearchEngine;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.equality.EqualityIndexDefinition;
import org.example.generalsearch.index.range.RangeIndexDefinition;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.model.ProductIndexDefinitions;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.schema.annotation.IndexType;
import org.example.generalsearch.schema.annotation.SearchId;
import org.example.generalsearch.schema.annotation.SearchIndex;
import org.junit.jupiter.api.Test;

class AnnotatedSchemaFactoryTest {
    @Test
    void generatesARecordSchemaEquivalentToTheManualProductSchema() {
        Product product = new Product(
                "p1", "Laptop", Category.ELECTRONICS, 999, true, 4.8);
        AnnotatedSearchConfiguration<Product, String> generated =
                AnnotatedSchemaFactory.create(Product.class, String.class);
        SearchSchema<Product, String> manual = manualProductSchema();

        assertEquals(manual.documentType(), generated.schema().documentType());
        assertEquals(manual.idField().name(), generated.schema().idField().name());
        assertEquals(manual.idField().valueType(), generated.schema().idField().valueType());
        assertEquals(manual.fields().keySet(), generated.schema().fields().keySet());
        manual.fields().forEach((name, field) -> {
            Field<Product, ?> actual = generated.schema().requireField(name);
            assertEquals(field.valueType(), actual.valueType());
            assertEquals(field.valueOf(product), actual.valueOf(product));
        });

        Map<String, Class<?>> indexesByField = generated.indexDefinitions().stream()
                .collect(Collectors.toMap(
                        definition -> definition.field().name(),
                        Object::getClass
                ));
        assertEquals(Map.of(
                "category", EqualityIndexDefinition.class,
                "price", RangeIndexDefinition.class,
                "prime", EqualityIndexDefinition.class
        ), indexesByField);
    }

    @Test
    void generatedProductFieldsAndIndexesShareCanonicalFieldInstances() {
        for (IndexDefinition<Product> definition : ProductIndexDefinitions.defaults()) {
            assertSame(
                    ProductFields.SCHEMA.requireField(definition.field().name()),
                    definition.field()
            );
        }
    }

    @Test
    void generatedConfigurationRunsThroughTheGenericEngine() {
        AnnotatedSearchConfiguration<Product, String> generated =
                AnnotatedSchemaFactory.create(Product.class, String.class);
        Field<Product, Category> category =
                generated.schema().requireField("category", Category.class);
        Field<Product, Double> price =
                generated.schema().requireField("price", Double.class);
        Product laptop = new Product(
                "p1", "Laptop", Category.ELECTRONICS, 999, true, 4.8);

        try (SearchEngine<String, Product> engine = new SnapshotSearchEngine<>(
                generated.schema(), generated.indexDefinitions())) {
            engine.add(laptop).join();

            assertEquals(List.of(laptop), engine.search(Query.and(
                    Query.eq(category, Category.ELECTRONICS),
                    Query.between(price, 900.0, 1_100.0)
            )));
        }
    }

    @Test
    void supportsPrivateFieldsGettersAndPrimitiveBoxing() {
        AnnotatedSearchConfiguration<Customer, Long> generated =
                AnnotatedSchemaFactory.create(Customer.class, Long.class);
        Customer customer = new Customer(7, "west", 82, true);

        assertEquals(Long.class, generated.schema().idField().valueType());
        assertEquals(7L, generated.schema().idOf(customer));
        assertEquals("west", generated.schema()
                .requireField("region", String.class)
                .valueOf(customer));
        assertEquals(82, generated.schema()
                .requireField("score", Integer.class)
                .valueOf(customer));
        assertEquals(true, generated.schema()
                .requireField("active", Boolean.class)
                .valueOf(customer));
        assertEquals(3, generated.indexDefinitions().size());
        assertTrue(generated.indexDefinitions().stream()
                .anyMatch(definition -> definition.field().name().equals("score")
                        && definition instanceof RangeIndexDefinition<?, ?>));
    }

    @Test
    void rejectsInvalidIdsAndDuplicateFieldNames() {
        assertThrows(SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(MissingId.class, Long.class));
        assertThrows(SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(MultipleIds.class, Long.class));
        assertThrows(SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(DuplicateName.class, Long.class));
        assertThrows(SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(Product.class, Long.class));
    }

    @Test
    void rejectsInvalidOrUnavailableIndexTypesAndInvalidMembers() {
        SchemaGenerationException rangeFailure = assertThrows(
                SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(InvalidRange.class, Long.class));
        assertTrue(rangeFailure.getMessage().contains("Comparable"));

        SchemaGenerationException prefixTypeFailure = assertThrows(
                SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(InvalidPrefixType.class, Long.class));
        assertTrue(prefixTypeFailure.getMessage().contains("String"));

        SchemaGenerationException unavailablePrefix = assertThrows(
                SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(UnavailablePrefix.class, Long.class));
        assertTrue(unavailablePrefix.getMessage().contains("not implemented"));

        assertThrows(SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(InvalidGetter.class, Long.class));
        assertThrows(SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(StaticField.class, Long.class));
        assertThrows(SchemaGenerationException.class,
                () -> AnnotatedSchemaFactory.create(WrongComparable.class, Long.class));
    }

    private static SearchSchema<Product, String> manualProductSchema() {
        Field<Product, String> id = Field.of("id", String.class, Product::id);
        return SearchSchema.builder(Product.class, id)
                .field(Field.of("name", String.class, Product::name))
                .field(Field.of("category", Category.class, Product::category))
                .field(Field.of("price", Double.class, Product::price))
                .field(Field.of("prime", Boolean.class, Product::prime))
                .field(Field.of("rating", Double.class, Product::rating))
                .build();
    }

    private static class IdentifiedCustomer {
        @SearchId
        private final long id;

        private IdentifiedCustomer(long id) {
            this.id = id;
        }
    }

    private static final class Customer extends IdentifiedCustomer {

        @SearchIndex(IndexType.EQUALITY)
        private final String region;

        private final int score;
        private final boolean active;

        private Customer(long id, String region, int score, boolean active) {
            super(id);
            this.region = region;
            this.score = score;
            this.active = active;
        }

        @SearchIndex(IndexType.RANGE)
        private int getScore() {
            return score;
        }

        @SearchIndex(IndexType.EQUALITY)
        private boolean isActive() {
            return active;
        }
    }

    private static final class MissingId {
        @SearchIndex(IndexType.EQUALITY)
        private String name;
    }

    private static final class MultipleIds {
        @SearchId
        private long first;

        @SearchId
        private long second;
    }

    private static final class DuplicateName {
        @SearchId
        private long id;

        @SearchIndex(IndexType.EQUALITY)
        private String name;

        @SearchIndex(IndexType.EQUALITY)
        private String getName() {
            return name;
        }
    }

    private static final class InvalidRange {
        @SearchId
        private long id;

        @SearchIndex(IndexType.RANGE)
        private Object payload;
    }

    private static final class InvalidPrefixType {
        @SearchId
        private long id;

        @SearchIndex(IndexType.PREFIX)
        private int code;
    }

    private static final class UnavailablePrefix {
        @SearchId
        private long id;

        @SearchIndex(IndexType.PREFIX)
        private String name;
    }

    private static final class InvalidGetter {
        @SearchId
        private long id;

        @SearchIndex(IndexType.EQUALITY)
        private String getValue(String argument) {
            return argument;
        }
    }

    private static final class StaticField {
        @SearchId
        private long id;

        @SearchIndex(IndexType.EQUALITY)
        private static String value;
    }

    private static final class WrongComparable {
        @SearchId
        private long id;

        @SearchIndex(IndexType.RANGE)
        private BadRangeValue value;
    }

    private static final class BadRangeValue implements Comparable<String> {
        @Override
        public int compareTo(String other) {
            return 0;
        }
    }
}
