package io.github.patricklfdm.generalsearch.index;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

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
                .min(Comparator
                        .comparingInt((CandidateResult result) ->
                                result.bitmap().cardinality())
                        .thenComparingInt(result ->
                                result.accuracy() == CandidateAccuracy.EXACT ? 0 : 1));
    }

    public List<IndexSnapshot<T>> indexes() {
        return indexes;
    }

    public boolean contains(Field<T, ?> field, Class<?> indexType) {
        Objects.requireNonNull(field, "field");
        Objects.requireNonNull(indexType, "indexType");
        return indexes.stream().anyMatch(index ->
                index.field() == field && index.getClass() == indexType);
    }

    public IndexRegistry<T> withIndex(IndexSnapshot<T> index) {
        Objects.requireNonNull(index, "index");
        if (contains(index.field(), index.getClass())) {
            throw new IllegalStateException(
                    "index already exists for field: " + index.field().name());
        }
        List<IndexSnapshot<T>> updated = new ArrayList<>(indexes);
        updated.add(index);
        return new IndexRegistry<>(updated);
    }

    public IndexRegistry<T> withoutIndexes(Field<T, ?> field) {
        Objects.requireNonNull(field, "field");
        List<IndexSnapshot<T>> updated = indexes.stream()
                .filter(index -> index.field() != field)
                .toList();
        return updated.size() == indexes.size() ? this : new IndexRegistry<>(updated);
    }

    public IndexRegistryBuilder<T> toBuilder() {
        return new IndexRegistryBuilder<>(this);
    }
}
