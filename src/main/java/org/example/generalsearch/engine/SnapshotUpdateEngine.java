package org.example.generalsearch.engine;

import java.util.Collection;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.filter.ProductFilter;
import org.example.generalsearch.filter.ProductFilterAdapter;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;
import org.example.generalsearch.model.ProductIndexDefinitions;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.storage.SearchSnapshot;

/**
 * Product convenience boundary backed by the generic snapshot search engine.
 */
public final class SnapshotUpdateEngine implements ProductSearchEngine {
    private final SnapshotSearchEngine<String, Product> delegate;

    public SnapshotUpdateEngine() {
        this(SnapshotEngineConfig.DEFAULT, ProductIndexDefinitions.defaults());
    }

    public SnapshotUpdateEngine(SnapshotEngineConfig config) {
        this(config, ProductIndexDefinitions.defaults());
    }

    public SnapshotUpdateEngine(
            SnapshotEngineConfig config,
            Collection<? extends IndexDefinition<Product>> indexDefinitions
    ) {
        delegate = new SnapshotSearchEngine<>(
                config,
                ProductFields.SCHEMA,
                indexDefinitions
        );
    }

    @Override
    public CompletableFuture<Void> add(Product document) {
        return delegate.add(document);
    }

    @Override
    public CompletableFuture<Void> update(Product document) {
        return delegate.update(document);
    }

    @Override
    public CompletableFuture<Void> remove(String id) {
        return delegate.remove(id);
    }

    @Override
    public CompletableFuture<Void> createIndex(IndexDefinition<Product> definition) {
        return delegate.createIndex(definition);
    }

    @Override
    public CompletableFuture<Void> dropIndex(String fieldName) {
        return delegate.dropIndex(fieldName);
    }

    @Override
    public Product get(String id) {
        return delegate.get(id);
    }

    @Override
    @SuppressWarnings("deprecation")
    public List<Product> search(Query<Product> query) {
        Query<Product> effectiveQuery = query instanceof ProductFilter productFilter
                ? ProductFilterAdapter.toQuery(productFilter)
                : query;
        return delegate.search(effectiveQuery);
    }

    SearchSnapshot<Product> snapshotForTesting() {
        return delegate.snapshotForTesting();
    }

    Integer internalDocIdForTesting(String id) {
        return delegate.internalDocIdForTesting(id);
    }

    @Override
    public void close() {
        delegate.close();
    }
}
