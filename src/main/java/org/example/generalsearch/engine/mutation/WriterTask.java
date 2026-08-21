package org.example.generalsearch.engine.mutation;

import java.util.concurrent.CompletableFuture;

public interface WriterTask<K, T> {
    CompletableFuture<Void> completion();
}
