package org.example.generalsearch.engine.mutation;

import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.index.IndexDefinition;

public record CreateIndexTask<K, T>(
        IndexDefinition<T> definition,
        CompletableFuture<Void> completion
) implements WriterTask<K, T> {
    public CreateIndexTask {
        Objects.requireNonNull(definition, "definition");
        Objects.requireNonNull(completion, "completion");
    }
}
