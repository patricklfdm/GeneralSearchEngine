package io.github.patricklfdm.generalsearch.index.range;

import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimateQuality;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.EqualQuery;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.RangeQuery;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class RangeIndexSnapshot<T, V extends Comparable<? super V>>
        implements EstimatingIndexSnapshot<T> {
    private final Field<T, V> field;
    private final PersistentAvlMap<V, ImmutableBitmap> values;
    private final IndexStatistics statistics;

    private RangeIndexSnapshot(
            Field<T, V> field,
            PersistentAvlMap<V, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Objects.requireNonNull(values, "values");
        this.statistics = new IndexStatistics(indexedDocumentCount, this.values.size());
    }

    public static <T, V extends Comparable<? super V>> RangeIndexSnapshot<T, V> empty(
            Field<T, V> field
    ) {
        return new RangeIndexSnapshot<>(field, PersistentAvlMap.empty(), 0);
    }

    static <T, V extends Comparable<? super V>> RangeIndexSnapshot<T, V> fromValues(
            Field<T, V> field,
            PersistentAvlMap<V, ImmutableBitmap> values,
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
                : valueOrEmpty(value);
    }

    public ImmutableBitmap getByRange(V minValue, V maxValue) {
        if (minValue.compareTo(maxValue) > 0) {
            return ImmutableBitmap.empty();
        }
        BitmapUnion union = new BitmapUnion();
        values.forEachInRange(minValue, true, maxValue, true,
                (ignored, bitmap) -> union.add(bitmap));
        return union.build();
    }

    @Override
    public Optional<CandidateResult> candidates(Query<T> query) {
        if (query instanceof EqualQuery<?, ?> equal && equal.field() == field) {
            if (equal.expectedValue() == null) {
                return Optional.empty();
            }
            // Ordered-map key identity is compareTo == 0, whereas EqualQuery uses
            // Objects.equals. Comparable types are allowed to make those semantics
            // differ (BigDecimal is the common example), so this is only a superset.
            return Optional.of(new CandidateResult(
                    valueOrEmpty(equal.expectedValue()),
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
            ImmutableBitmap bitmap = values.get(value(equal.expectedValue()));
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
            CardinalityCounter counter = new CardinalityCounter();
            values.forEachInRange(minValue, true, maxValue, true,
                    (ignored, bitmap) -> counter.add(bitmap));
            return Optional.of(estimate(
                    counter.cardinality,
                    counter.sourceCount,
                    CandidateAccuracy.EXACT
            ));
        }
        return Optional.empty();
    }

    @Override
    public IndexBuilder<T> toBuilder() {
        return new RangeIndexBuilder<>(this);
    }

    PersistentAvlMap<V, ImmutableBitmap> values() {
        return values;
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

    private ImmutableBitmap valueOrEmpty(Object value) {
        ImmutableBitmap bitmap = values.get(value(value));
        return bitmap == null ? ImmutableBitmap.empty() : bitmap;
    }

    private static final class BitmapUnion {
        private ImmutableBitmap first;
        private ImmutableBitmapBuilder builder;

        private void add(ImmutableBitmap bitmap) {
            if (first == null) {
                first = bitmap;
            } else {
                if (builder == null) {
                    builder = new ImmutableBitmapBuilder(first);
                }
                builder.or(bitmap);
            }
        }

        private ImmutableBitmap build() {
            if (first == null) {
                return ImmutableBitmap.empty();
            }
            return builder == null ? first : builder.build();
        }
    }

    private static final class CardinalityCounter {
        private int cardinality;
        private int sourceCount;

        private void add(ImmutableBitmap bitmap) {
            cardinality = Math.addExact(cardinality, bitmap.cardinality());
            sourceCount++;
        }
    }
}
