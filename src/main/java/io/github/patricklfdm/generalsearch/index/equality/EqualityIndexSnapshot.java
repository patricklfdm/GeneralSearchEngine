package io.github.patricklfdm.generalsearch.index.equality;

import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimateQuality;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
import io.github.patricklfdm.generalsearch.internal.index.ImmutableOverlayMap;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.EqualQuery;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class EqualityIndexSnapshot<T, V> implements EstimatingIndexSnapshot<T> {
    private final Field<T, V> field;
    private final ImmutableOverlayMap<V, ImmutableBitmap> values;
    private final IndexStatistics statistics;

    private EqualityIndexSnapshot(
            Field<T, V> field,
            ImmutableOverlayMap<V, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Objects.requireNonNull(values, "values");
        this.statistics = new IndexStatistics(indexedDocumentCount, this.values.size());
    }

    public static <T, V> EqualityIndexSnapshot<T, V> empty(Field<T, V> field) {
        return new EqualityIndexSnapshot<>(field, ImmutableOverlayMap.empty(), 0);
    }

    static <T, V> EqualityIndexSnapshot<T, V> fromValues(
            Field<T, V> field,
            ImmutableOverlayMap<V, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        return new EqualityIndexSnapshot<>(field, values, indexedDocumentCount);
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
                valueOrEmpty(equal.expectedValue()),
                CandidateAccuracy.EXACT
        ));
    }

    @Override
    public IndexStatistics statistics() {
        return statistics;
    }

    @Override
    public Optional<CandidateEstimate> estimateCandidates(Query<T> query) {
        Objects.requireNonNull(query, "query");
        if (!(query instanceof EqualQuery<?, ?> equal)
                || equal.field() != field
                || equal.expectedValue() == null) {
            return Optional.empty();
        }
        ImmutableBitmap bitmap = values.get(value(equal.expectedValue()));
        return Optional.of(new CandidateEstimate(
                bitmap == null ? 0 : bitmap.cardinality(),
                bitmap == null ? 0 : 1,
                EstimateQuality.EXACT,
                CandidateAccuracy.EXACT
        ));
    }

    @Override
    public IndexBuilder<T> toBuilder() {
        return new EqualityIndexBuilder<>(this);
    }

    ImmutableOverlayMap<V, ImmutableBitmap> values() {
        return values;
    }

    private ImmutableBitmap valueOrEmpty(Object value) {
        ImmutableBitmap bitmap = values.get(value(value));
        return bitmap == null ? ImmutableBitmap.empty() : bitmap;
    }

    @SuppressWarnings("unchecked")
    private V value(Object value) {
        return (V) value;
    }
}
