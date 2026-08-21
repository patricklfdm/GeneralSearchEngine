package io.github.patricklfdm.generalsearch.index.equality;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.EqualQuery;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class EqualityIndexSnapshot<T, V> implements IndexSnapshot<T> {
    private final Field<T, V> field;
    private final Map<V, ImmutableBitmap> values;

    private EqualityIndexSnapshot(Field<T, V> field, Map<V, ImmutableBitmap> values) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Map.copyOf(values);
    }

    public static <T, V> EqualityIndexSnapshot<T, V> empty(Field<T, V> field) {
        return new EqualityIndexSnapshot<>(field, Map.of());
    }

    static <T, V> EqualityIndexSnapshot<T, V> fromOwnedValues(
            Field<T, V> field,
            Map<V, ImmutableBitmap> values
    ) {
        return new EqualityIndexSnapshot<>(field, values);
    }

    @Override
    public Field<T, V> field() {
        return field;
    }

    public ImmutableBitmap get(V value) {
        return value == null
                ? ImmutableBitmap.empty()
                : values.getOrDefault(value, ImmutableBitmap.empty());
    }

    @Override
    public Optional<CandidateResult> candidates(Query<T> query) {
        if (!(query instanceof EqualQuery<?, ?> equal) || equal.field() != field) {
            return Optional.empty();
        }
        if (equal.expectedValue() == null) {
            // Null values are not indexed, so scanning is required to preserve correctness.
            return Optional.empty();
        }
        return Optional.of(new CandidateResult(
                values.getOrDefault(equal.expectedValue(), ImmutableBitmap.empty()),
                CandidateAccuracy.EXACT
        ));
    }

    @Override
    public IndexBuilder<T> toBuilder() {
        return new EqualityIndexBuilder<>(this);
    }

    Map<V, ImmutableBitmap> copyValues() {
        return new HashMap<>(values);
    }
}
