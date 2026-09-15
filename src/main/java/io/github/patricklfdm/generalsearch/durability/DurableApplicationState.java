package io.github.patricklfdm.generalsearch.durability;

import java.util.List;
import java.util.Objects;
import java.util.UUID;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;

/**
 * Canonically ordered application state for standalone backup transfer.
 * Lists are immutable; documents retain the engine's immutable-document obligation.
 * This value alone confers no storage or replication authority.
 */
public record DurableApplicationState<T>(
        UUID history,
        long sequence,
        List<T> documents,
        List<IndexDefinition<T>> indexes
) {
    public DurableApplicationState {
        Objects.requireNonNull(history, "history");
        if (history.equals(new UUID(0, 0)) || sequence < 0) {
            throw new IllegalArgumentException("history must be nonzero and sequence nonnegative");
        }
        documents = List.copyOf(documents);
        indexes = List.copyOf(indexes);
    }
}
