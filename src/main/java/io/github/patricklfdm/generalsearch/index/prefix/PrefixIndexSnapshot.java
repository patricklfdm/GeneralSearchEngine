package io.github.patricklfdm.generalsearch.index.prefix;

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
import io.github.patricklfdm.generalsearch.query.PrefixQuery;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class PrefixIndexSnapshot<T> implements EstimatingIndexSnapshot<T> {
    private final Field<T, String> field;
    private final PersistentAvlMap<String, ImmutableBitmap> values;
    private final IndexStatistics statistics;

    private PrefixIndexSnapshot(
            Field<T, String> field,
            PersistentAvlMap<String, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Objects.requireNonNull(values, "values");
        this.statistics = new IndexStatistics(indexedDocumentCount, this.values.size());
    }

    public static <T> PrefixIndexSnapshot<T> empty(Field<T, String> field) {
        return new PrefixIndexSnapshot<>(field, PersistentAvlMap.empty(), 0);
    }

    static <T> PrefixIndexSnapshot<T> fromValues(
            Field<T, String> field,
            PersistentAvlMap<String, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        return new PrefixIndexSnapshot<>(field, values, indexedDocumentCount);
    }

    @Override
    public Field<T, String> field() {
        return field;
    }

    public ImmutableBitmap get(String value) {
        return value == null
                ? ImmutableBitmap.empty()
                : valueOrEmpty(value);
    }

    public ImmutableBitmap getByPrefix(String prefix) {
        Objects.requireNonNull(prefix, "prefix");
        BitmapUnion union = new BitmapUnion();
        forEachMatching(prefix, (ignored, bitmap) -> union.add(bitmap));
        return union.build();
    }

    @Override
    public Optional<CandidateResult> candidates(Query<T> query) {
        if (query instanceof PrefixQuery<?> prefix && prefix.field() == field) {
            return exact(getByPrefix(prefix.prefix()));
        }
        if (query instanceof EqualQuery<?, ?> equal && equal.field() == field) {
            if (equal.expectedValue() == null) {
                return Optional.empty();
            }
            return exact(get((String) equal.expectedValue()));
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
        if (query instanceof PrefixQuery<?> prefix && prefix.field() == field) {
            CardinalityCounter counter = new CardinalityCounter();
            forEachMatching(prefix.prefix(), (ignored, bitmap) -> counter.add(bitmap));
            return Optional.of(new CandidateEstimate(
                    counter.cardinality,
                    counter.sourceCount,
                    EstimateQuality.EXACT,
                    CandidateAccuracy.EXACT
            ));
        }
        if (query instanceof EqualQuery<?, ?> equal && equal.field() == field) {
            if (equal.expectedValue() == null) {
                return Optional.empty();
            }
            ImmutableBitmap bitmap = values.get((String) equal.expectedValue());
            return Optional.of(new CandidateEstimate(
                    bitmap == null ? 0 : bitmap.cardinality(),
                    bitmap == null ? 0 : 1,
                    EstimateQuality.EXACT,
                    CandidateAccuracy.EXACT
            ));
        }
        return Optional.empty();
    }

    @Override
    public IndexBuilder<T> toBuilder() {
        return new PrefixIndexBuilder<>(this);
    }

    PersistentAvlMap<String, ImmutableBitmap> values() {
        return values;
    }

    private void forEachMatching(
            String prefix,
            java.util.function.BiConsumer<? super String, ? super ImmutableBitmap> consumer
    ) {
        if (prefix.isEmpty()) {
            values.forEachInRange(null, true, null, true, consumer);
            return;
        }
        String upperBound = exclusiveUpperBound(prefix);
        values.forEachInRange(prefix, true, upperBound, false, consumer);
    }

    private static String exclusiveUpperBound(String prefix) {
        char[] characters = prefix.toCharArray();
        for (int index = characters.length - 1; index >= 0; index--) {
            if (characters[index] != Character.MAX_VALUE) {
                characters[index]++;
                return new String(characters, 0, index + 1);
            }
        }
        return null;
    }

    private Optional<CandidateResult> exact(ImmutableBitmap bitmap) {
        return Optional.of(new CandidateResult(bitmap, CandidateAccuracy.EXACT));
    }

    private ImmutableBitmap valueOrEmpty(Object value) {
        ImmutableBitmap bitmap = values.get((String) value);
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
