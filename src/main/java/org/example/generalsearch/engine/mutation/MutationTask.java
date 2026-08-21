package org.example.generalsearch.engine.mutation;

import java.util.Objects;
import java.util.concurrent.CompletableFuture;

public record MutationTask<K, T>(
        SearchMutation<K, T> mutation,
        CompletableFuture<Void> completion
) {
    public MutationTask {
        Objects.requireNonNull(mutation, "mutation");
        Objects.requireNonNull(completion, "completion");
    }
}
