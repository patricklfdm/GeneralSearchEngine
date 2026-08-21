package org.example.generalsearch.engine.mutation;

import java.util.Objects;
import java.util.concurrent.CompletableFuture;

public record DropIndexTask<K, T>(
        String fieldName,
        CompletableFuture<Void> completion
) implements WriterTask<K, T> {
    public DropIndexTask {
        if (fieldName == null || fieldName.isBlank()) {
            throw new IllegalArgumentException("fieldName must not be blank");
        }
        Objects.requireNonNull(completion, "completion");
    }
}
