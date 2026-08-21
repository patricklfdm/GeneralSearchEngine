package org.example.generalsearch.engine;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.query.Query;

public interface ProductSearchEngine extends AutoCloseable {
    CompletableFuture<Void> add(int docId, Product product);

    CompletableFuture<Void> update(int docId, Product product);

    CompletableFuture<Void> remove(int docId);

    Product get(int docId);

    List<Product> search(Query<Product> query);

    @Override
    void close();
}
