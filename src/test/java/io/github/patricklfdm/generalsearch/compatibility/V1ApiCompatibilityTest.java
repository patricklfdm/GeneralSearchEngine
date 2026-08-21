package io.github.patricklfdm.generalsearch.compatibility;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.time.Duration;
import java.util.Collection;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import io.github.patricklfdm.generalsearch.engine.SearchEngine;
import io.github.patricklfdm.generalsearch.engine.SearchEngineBuilder;
import io.github.patricklfdm.generalsearch.engine.SnapshotEngineConfig;
import io.github.patricklfdm.generalsearch.engine.SnapshotSearchEngine;
import io.github.patricklfdm.generalsearch.engine.SnapshotUpdateEngine;
import io.github.patricklfdm.generalsearch.engine.exception.DocumentAlreadyExistsException;
import io.github.patricklfdm.generalsearch.engine.exception.DocumentNotFoundException;
import io.github.patricklfdm.generalsearch.engine.exception.EngineRejectedExecutionException;
import io.github.patricklfdm.generalsearch.engine.exception.IndexLifecycleException;
import io.github.patricklfdm.generalsearch.engine.metrics.SearchEngineMetrics;
import io.github.patricklfdm.generalsearch.filter.NameFilter;
import io.github.patricklfdm.generalsearch.filter.ProductFilter;
import io.github.patricklfdm.generalsearch.filter.ProductFilterAdapter;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.index.equality.EqualityIndexDefinition;
import io.github.patricklfdm.generalsearch.index.prefix.PrefixIndexDefinition;
import io.github.patricklfdm.generalsearch.index.range.RangeIndexDefinition;
import io.github.patricklfdm.generalsearch.model.Category;
import io.github.patricklfdm.generalsearch.model.Product;
import io.github.patricklfdm.generalsearch.model.ProductFields;
import io.github.patricklfdm.generalsearch.model.ProductIndexDefinitions;
import io.github.patricklfdm.generalsearch.query.AndQuery;
import io.github.patricklfdm.generalsearch.query.EqualQuery;
import io.github.patricklfdm.generalsearch.query.MatchAllQuery;
import io.github.patricklfdm.generalsearch.query.NotQuery;
import io.github.patricklfdm.generalsearch.query.OrQuery;
import io.github.patricklfdm.generalsearch.query.PrefixQuery;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.RangeQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.SearchSchema;
import io.github.patricklfdm.generalsearch.schema.annotation.IndexType;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchId;
import io.github.patricklfdm.generalsearch.schema.annotation.SearchIndex;
import org.junit.jupiter.api.Test;

/**
 * Compile-time consumer fixture plus key erased JVM descriptor checks for the supported v1 API.
 * Additive APIs are allowed; changing or removing a listed contract must be a major-version
 * decision and requires an intentional update to this fixture.
 */
@SuppressWarnings("deprecation")
class V1ApiCompatibilityTest {
    @Test
    void genericApplicationSurfaceCompilesAndOperates() {
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, String> name = Field.of("name", String.class, Item::name);
        Field<Item, Integer> quantity =
                Field.of("quantity", Integer.class, Item::quantity);
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(name)
                .field(quantity)
                .build();
        SnapshotEngineConfig config =
                new SnapshotEngineConfig(100, 10, Duration.ZERO);

        try (SearchEngine<Long, Item> engine = SearchEngine.builder(schema)
                .indexes(List.of(
                        IndexDefinition.equality(name),
                        IndexDefinition.prefix(name)))
                .index(IndexDefinition.range(quantity))
                .config(config)
                .build()) {
            Item item = new Item(1L, "Cable", 5);
            CompletableFuture<Void> add = engine.add(item);
            add.join();

            EqualQuery<Item, String> equality = Query.eq(name, "Cable");
            RangeQuery<Item, Integer> range = Query.between(quantity, 1, 10);
            PrefixQuery<Item> prefix = Query.prefix(name, "Cab");
            AndQuery<Item> and = Query.and(equality, range);
            OrQuery<Item> or = Query.or(List.of(prefix, Query.not(range)));
            NotQuery<Item> not = Query.not(equality);
            MatchAllQuery<Item> all = Query.matchAll();

            assertEquals(List.of(item), engine.search(and));
            assertEquals(List.of(item), engine.search(or));
            assertEquals(List.of(), engine.search(not));
            assertEquals(List.of(item), engine.search(all));
            assertEquals(item, engine.get(1L));
            assertEquals(schema, engine.schema());
            SearchEngineMetrics metrics = engine.metrics();
            assertEquals(1, metrics.documentCount());
            assertEquals(3, metrics.registeredIndexCount());

            engine.update(new Item(1L, "Cable", 6)).join();
            engine.createIndex(IndexDefinition.equality(quantity)).join();
            engine.dropIndex("quantity").join();
            engine.remove(1L).join();
        }
    }

    @Test
    void factoryConcreteAndProductCompatibilityEntrypointsRemainUsable() {
        Field<Item, Long> id = Field.of("id", Long.class, Item::id);
        Field<Item, String> name = Field.of("name", String.class, Item::name);
        SearchSchema<Item, Long> schema = SearchSchema.builder(Item.class, id)
                .field(name)
                .build();

        try (SearchEngine<Long, Item> ignored = SearchEngine.builder(Item.class, id)
                .field(name)
                .build();
             SearchEngine<Long, AnnotatedItem> ignoredAnnotated =
                     SearchEngine.annotatedBuilder(AnnotatedItem.class, Long.class)
                             .config(SnapshotEngineConfig.DEFAULT)
                             .build();
             SearchEngine<Long, AnnotatedItem> ignoredFactory =
                     SearchEngine.fromAnnotatedClass(AnnotatedItem.class, Long.class);
             SnapshotSearchEngine<Long, Item> ignoredConcrete =
                     new SnapshotSearchEngine<>(schema, List.of());
             SnapshotSearchEngine<Long, Item> ignoredConfigured =
                     new SnapshotSearchEngine<>(
                             SnapshotEngineConfig.DEFAULT, schema, List.of());
             SnapshotUpdateEngine productDefault = new SnapshotUpdateEngine();
             SnapshotUpdateEngine productConfigured =
                     new SnapshotUpdateEngine(SnapshotEngineConfig.DEFAULT);
             SnapshotUpdateEngine productIndexes = new SnapshotUpdateEngine(
                     SnapshotEngineConfig.DEFAULT,
                     ProductIndexDefinitions.defaults())) {
            Product product = new Product(
                    "p1", "Phone", Category.ELECTRONICS, 100.0, true, 4.0);
            productDefault.add(product).join();
            ProductFilter legacy = new NameFilter("Pho");
            Query<Product> adapted = ProductFilterAdapter.toQuery(legacy);
            assertEquals(List.of(product), productDefault.search(adapted));
            assertNotNull(ProductFields.SCHEMA);
        }
    }

    @Test
    void supportedErasedJvmDescriptorsRemainAvailable() throws Exception {
        assertMethod(SearchEngine.class, "builder", SearchEngineBuilder.class,
                SearchSchema.class);
        assertMethod(SearchEngine.class, "builder", SearchEngineBuilder.class,
                Class.class, Field.class);
        assertMethod(SearchEngine.class, "annotatedBuilder", SearchEngineBuilder.class,
                Class.class, Class.class);
        assertMethod(SearchEngine.class, "fromAnnotatedClass", SearchEngine.class,
                Class.class, Class.class);
        assertMethod(SearchEngine.class, "add", CompletableFuture.class, Object.class);
        assertMethod(SearchEngine.class, "update", CompletableFuture.class, Object.class);
        assertMethod(SearchEngine.class, "remove", CompletableFuture.class, Object.class);
        assertMethod(SearchEngine.class, "createIndex", CompletableFuture.class,
                IndexDefinition.class);
        assertMethod(SearchEngine.class, "dropIndex", CompletableFuture.class,
                String.class);
        assertMethod(SearchEngine.class, "get", Object.class, Object.class);
        assertMethod(SearchEngine.class, "search", List.class, Query.class);
        assertMethod(SearchEngine.class, "schema", SearchSchema.class);
        assertMethod(SearchEngine.class, "metrics", SearchEngineMetrics.class);
        assertMethod(SearchEngine.class, "close", void.class);

        assertMethod(SearchEngineBuilder.class, "field", SearchEngineBuilder.class,
                Field.class);
        assertMethod(SearchEngineBuilder.class, "index", SearchEngineBuilder.class,
                IndexDefinition.class);
        assertMethod(SearchEngineBuilder.class, "indexes", SearchEngineBuilder.class,
                Collection.class);
        assertMethod(SearchEngineBuilder.class, "config", SearchEngineBuilder.class,
                SnapshotEngineConfig.class);
        assertMethod(SearchEngineBuilder.class, "build", SearchEngine.class);

        assertConstructor(SnapshotSearchEngine.class, SearchSchema.class, Collection.class);
        assertConstructor(SnapshotSearchEngine.class, SnapshotEngineConfig.class,
                SearchSchema.class, Collection.class);
        assertConstructor(SnapshotUpdateEngine.class);
        assertConstructor(SnapshotUpdateEngine.class, SnapshotEngineConfig.class);
        assertConstructor(SnapshotUpdateEngine.class, SnapshotEngineConfig.class,
                Collection.class);

        assertMethod(Query.class, "eq", EqualQuery.class, Field.class, Object.class);
        assertMethod(Query.class, "between", RangeQuery.class,
                Field.class, Comparable.class, Comparable.class);
        assertMethod(Query.class, "prefix", PrefixQuery.class, Field.class, String.class);
        assertMethod(Query.class, "and", AndQuery.class, Query[].class);
        assertMethod(Query.class, "and", AndQuery.class, List.class);
        assertMethod(Query.class, "or", OrQuery.class, Query[].class);
        assertMethod(Query.class, "or", OrQuery.class, List.class);
        assertMethod(Query.class, "not", NotQuery.class, Query.class);
        assertMethod(Query.class, "matchAll", MatchAllQuery.class);

        assertMethod(IndexDefinition.class, "field", Field.class);
        assertMethod(IndexDefinition.class, "createEmpty", IndexSnapshot.class);
        assertMethod(IndexDefinition.class, "equality", EqualityIndexDefinition.class,
                Field.class);
        assertMethod(IndexDefinition.class, "range", RangeIndexDefinition.class,
                Field.class);
        assertMethod(IndexDefinition.class, "prefix", PrefixIndexDefinition.class,
                Field.class);
        assertMethod(IndexSnapshot.class, "field", Field.class);
        assertMethod(IndexSnapshot.class, "candidates", java.util.Optional.class,
                Query.class);
        assertMethod(IndexSnapshot.class, "toBuilder", IndexBuilder.class);
        assertMethod(IndexBuilder.class, "add", void.class, int.class, Object.class);
        assertMethod(IndexBuilder.class, "remove", void.class, int.class, Object.class);
        assertMethod(IndexBuilder.class, "update", void.class,
                int.class, Object.class, Object.class);
        assertMethod(IndexBuilder.class, "build", IndexSnapshot.class);

        assertConstructor(DocumentAlreadyExistsException.class, Object.class);
        assertConstructor(DocumentNotFoundException.class, Object.class);
        assertConstructor(EngineRejectedExecutionException.class,
                EngineRejectedExecutionException.Reason.class);
        assertConstructor(IndexLifecycleException.class,
                String.class, IndexLifecycleException.Reason.class);
        assertFalse(List.of(EngineRejectedExecutionException.Reason.values()).isEmpty());
        assertFalse(List.of(IndexLifecycleException.Reason.values()).isEmpty());
    }

    private static void assertMethod(
            Class<?> owner,
            String name,
            Class<?> returnType,
            Class<?>... parameterTypes
    ) throws Exception {
        Method method = owner.getMethod(name, parameterTypes);
        assertEquals(returnType, method.getReturnType(), method.toGenericString());
    }

    private static void assertConstructor(
            Class<?> owner,
            Class<?>... parameterTypes
    ) throws Exception {
        Constructor<?> constructor = owner.getConstructor(parameterTypes);
        assertNotNull(constructor);
    }

    private record Item(long id, String name, int quantity) {}

    private record AnnotatedItem(
            @SearchId long id,
            @SearchIndex(IndexType.PREFIX) String name
    ) {}
}
