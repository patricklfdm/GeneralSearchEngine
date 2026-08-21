package org.example.generalsearch.index;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import org.example.generalsearch.query.CandidateResult;
import org.example.generalsearch.query.Query;

public final class IndexRegistry<T> {
    private final List<IndexSnapshot<T>> indexes;

    private IndexRegistry(List<IndexSnapshot<T>> indexes) {
        this.indexes = List.copyOf(indexes);
    }

    public static <T> IndexRegistry<T> create(
            Collection<? extends IndexDefinition<T>> definitions
    ) {
        Objects.requireNonNull(definitions, "definitions");
        List<IndexSnapshot<T>> indexes = new ArrayList<>(definitions.size());
        for (IndexDefinition<T> definition : definitions) {
            IndexSnapshot<T> candidate =
                    Objects.requireNonNull(definition, "definition").createEmpty();
            boolean duplicate = indexes.stream().anyMatch(existing ->
                    existing.field() == candidate.field()
                            && existing.getClass() == candidate.getClass());
            if (duplicate) {
                throw new IllegalArgumentException(
                        "duplicate index for field: " + candidate.field().name());
            }
            indexes.add(candidate);
        }
        return new IndexRegistry<>(indexes);
    }

    static <T> IndexRegistry<T> fromSnapshots(List<IndexSnapshot<T>> indexes) {
        return new IndexRegistry<>(indexes);
    }

    public Optional<CandidateResult> candidates(Query<T> query) {
        Objects.requireNonNull(query, "query");
        return indexes.stream()
                .map(index -> index.candidates(query))
                .flatMap(Optional::stream)
                .min(Comparator.comparingInt(result -> result.bitmap().cardinality()));
    }

    public List<IndexSnapshot<T>> indexes() {
        return indexes;
    }

    public IndexRegistryBuilder<T> toBuilder() {
        return new IndexRegistryBuilder<>(this);
    }
}
