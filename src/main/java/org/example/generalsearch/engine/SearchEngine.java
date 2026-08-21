package org.example.generalsearch.engine;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.query.Query;

public interface SearchEngine<K, T> extends AutoCloseable {
    CompletableFuture<Void> add(T document);

    CompletableFuture<Void> update(T document);

    CompletableFuture<Void> remove(K id);

    T get(K id);

    List<T> search(Query<T> query);

    @Override
    void close();
}
