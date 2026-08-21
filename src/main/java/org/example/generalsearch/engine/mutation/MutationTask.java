package org.example.generalsearch.engine.mutation;

import java.util.Objects;
import java.util.concurrent.CompletableFuture;

public record MutationTask(CatalogMutation mutation, CompletableFuture<Void> completion) {
    public MutationTask {
        Objects.requireNonNull(mutation, "mutation");
        Objects.requireNonNull(completion, "completion");
    }
}
