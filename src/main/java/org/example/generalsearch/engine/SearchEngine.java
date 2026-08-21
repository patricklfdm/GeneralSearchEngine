package org.example.generalsearch.engine;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.query.Query;

public interface SearchEngine<K, T> extends AutoCloseable {
    CompletableFuture<Void> add(T document);

    CompletableFuture<Void> update(T document);

    CompletableFuture<Void> remove(K id);

    /**
     * Builds and atomically publishes an index without blocking readers or mutations.
     * Completion means the index is visible to new searches.
     */
    CompletableFuture<Void> createIndex(IndexDefinition<T> definition);

    /**
     * Removes every index registered for a canonical schema field name.
     * Dropping a known field without indexes is idempotent.
     */
    CompletableFuture<Void> dropIndex(String fieldName);

    T get(K id);

    List<T> search(Query<T> query);

    @Override
    void close();
}
