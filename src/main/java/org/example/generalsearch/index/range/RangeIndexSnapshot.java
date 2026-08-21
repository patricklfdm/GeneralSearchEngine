package org.example.generalsearch.index.range;

import java.util.Collections;
import java.util.NavigableMap;
import java.util.Objects;
import java.util.Optional;
import java.util.TreeMap;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.index.IndexBuilder;
import org.example.generalsearch.index.IndexSnapshot;
import org.example.generalsearch.query.CandidateAccuracy;
import org.example.generalsearch.query.CandidateResult;
import org.example.generalsearch.query.EqualQuery;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.query.RangeQuery;
import org.example.generalsearch.schema.Field;

public final class RangeIndexSnapshot<T, V extends Comparable<? super V>>
        implements IndexSnapshot<T> {
    private final Field<T, V> field;
    private final NavigableMap<V, ImmutableBitmap> values;

    private RangeIndexSnapshot(
            Field<T, V> field,
            NavigableMap<V, ImmutableBitmap> values
    ) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Collections.unmodifiableNavigableMap(new TreeMap<>(values));
    }

    public static <T, V extends Comparable<? super V>> RangeIndexSnapshot<T, V> empty(
            Field<T, V> field
    ) {
        return new RangeIndexSnapshot<>(field, new TreeMap<>());
    }

    static <T, V extends Comparable<? super V>> RangeIndexSnapshot<T, V> fromOwnedValues(
            Field<T, V> field,
            NavigableMap<V, ImmutableBitmap> values
    ) {
        return new RangeIndexSnapshot<>(field, values);
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

    public ImmutableBitmap getByRange(V minValue, V maxValue) {
        if (minValue.compareTo(maxValue) > 0) {
            return ImmutableBitmap.empty();
        }
        ImmutableBitmap result = ImmutableBitmap.empty();
        for (ImmutableBitmap bitmap
                : values.subMap(minValue, true, maxValue, true).values()) {
            result = result.or(bitmap);
        }
        return result;
    }

    @Override
    public Optional<CandidateResult> candidates(Query<T> query) {
        if (query instanceof EqualQuery<?, ?> equal && equal.field() == field) {
            if (equal.expectedValue() == null) {
                return Optional.empty();
            }
            return exact(values.getOrDefault(equal.expectedValue(), ImmutableBitmap.empty()));
        }
        if (query instanceof RangeQuery<?, ?> range && range.field() == field) {
            return exact(getByRange(value(range.minValue()), value(range.maxValue())));
        }
        return Optional.empty();
    }

    @Override
    public IndexBuilder<T> toBuilder() {
        return new RangeIndexBuilder<>(this);
    }

    TreeMap<V, ImmutableBitmap> copyValues() {
        return new TreeMap<>(values);
    }

    private Optional<CandidateResult> exact(ImmutableBitmap bitmap) {
        return Optional.of(new CandidateResult(bitmap, CandidateAccuracy.EXACT));
    }

    @SuppressWarnings("unchecked")
    private V value(Object value) {
        return (V) value;
    }
}
