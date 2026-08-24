package io.github.patricklfdm.generalsearch.index.range;

import java.util.Collections;
import java.util.NavigableMap;
import java.util.Objects;
import java.util.Optional;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimateQuality;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.EqualQuery;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.RangeQuery;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class RangeIndexSnapshot<T, V extends Comparable<? super V>>
        implements EstimatingIndexSnapshot<T> {
    private final Field<T, V> field;
    private final NavigableMap<V, ImmutableBitmap> values;
    private final IndexStatistics statistics;

    private RangeIndexSnapshot(
            Field<T, V> field,
            NavigableMap<V, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Collections.unmodifiableNavigableMap(new TreeMap<>(values));
        this.statistics = new IndexStatistics(indexedDocumentCount, this.values.size());
    }

    public static <T, V extends Comparable<? super V>> RangeIndexSnapshot<T, V> empty(
            Field<T, V> field
    ) {
        return new RangeIndexSnapshot<>(field, new TreeMap<>(), 0);
    }

    static <T, V extends Comparable<? super V>> RangeIndexSnapshot<T, V> fromOwnedValues(
            Field<T, V> field,
            NavigableMap<V, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        return new RangeIndexSnapshot<>(field, values, indexedDocumentCount);
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
            // TreeMap key identity is compareTo == 0, whereas EqualQuery uses
            // Objects.equals. Comparable types are allowed to make those semantics
            // differ (BigDecimal is the common example), so this is only a superset.
            return Optional.of(new CandidateResult(
                    values.getOrDefault(equal.expectedValue(), ImmutableBitmap.empty()),
                    CandidateAccuracy.SUPERSET
            ));
        }
        if (query instanceof RangeQuery<?, ?> range && range.field() == field) {
            return exact(getByRange(value(range.minValue()), value(range.maxValue())));
        }
        return Optional.empty();
    }

    @Override
    public IndexStatistics statistics() {
        return statistics;
    }

    @Override
    public Optional<CandidateEstimate> estimateCandidates(Query<T> query) {
        Objects.requireNonNull(query, "query");
        if (query instanceof EqualQuery<?, ?> equal && equal.field() == field) {
            if (equal.expectedValue() == null) {
                return Optional.empty();
            }
            ImmutableBitmap bitmap = values.get(equal.expectedValue());
            return Optional.of(estimate(
                    bitmap == null ? 0 : bitmap.cardinality(),
                    bitmap == null ? 0 : 1,
                    CandidateAccuracy.SUPERSET
            ));
        }
        if (query instanceof RangeQuery<?, ?> range && range.field() == field) {
            V minValue = value(range.minValue());
            V maxValue = value(range.maxValue());
            if (minValue.compareTo(maxValue) > 0) {
                return Optional.of(estimate(0, 0, CandidateAccuracy.EXACT));
            }
            int cardinality = 0;
            int sourceCount = 0;
            for (ImmutableBitmap bitmap
                    : values.subMap(minValue, true, maxValue, true).values()) {
                cardinality = Math.addExact(cardinality, bitmap.cardinality());
                sourceCount++;
            }
            return Optional.of(estimate(
                    cardinality,
                    sourceCount,
                    CandidateAccuracy.EXACT
            ));
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

    private CandidateEstimate estimate(
            int cardinality,
            int sourceCount,
            CandidateAccuracy accuracy
    ) {
        return new CandidateEstimate(
                cardinality,
                sourceCount,
                EstimateQuality.EXACT,
                accuracy
        );
    }

    @SuppressWarnings("unchecked")
    private V value(Object value) {
        return (V) value;
    }
}
