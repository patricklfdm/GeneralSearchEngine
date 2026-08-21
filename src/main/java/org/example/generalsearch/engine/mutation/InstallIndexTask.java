package org.example.generalsearch.engine.mutation;

import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import org.example.generalsearch.index.IndexSnapshot;

public record InstallIndexTask<K, T>(
        long buildId,
        IndexSnapshot<T> index,
        Throwable failure,
        CompletableFuture<Void> completion
) implements WriterTask<K, T> {
    public InstallIndexTask {
        if (buildId < 0) {
            throw new IllegalArgumentException("buildId must not be negative");
        }
        if ((index == null) == (failure == null)) {
            throw new IllegalArgumentException(
                    "exactly one of index or failure must be present");
        }
        Objects.requireNonNull(completion, "completion");
    }
}
