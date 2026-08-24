package io.github.patricklfdm.generalsearch.index.prefix;

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
import io.github.patricklfdm.generalsearch.query.PrefixQuery;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class PrefixIndexSnapshot<T> implements EstimatingIndexSnapshot<T> {
    private final Field<T, String> field;
    private final NavigableMap<String, ImmutableBitmap> values;
    private final IndexStatistics statistics;

    private PrefixIndexSnapshot(
            Field<T, String> field,
            NavigableMap<String, ImmutableBitmap> values,
            int indexedDocumentCount
    ) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Collections.unmodifiableNavigableMap(new TreeMap<>(values));
        this.statistics = new IndexStatistics(indexedDocumentCount, this.values.size());
    }

    public static <T> PrefixIndexSnapshot<T> empty(Field<T, String> field) {
        return new PrefixIndexSnapshot<>(field, new TreeMap<>(), 0);
    }

    static <T> PrefixIndexSnapshot<T> fromOwnedValues(
            Field<T, String> field,
            NavigableMap<String, ImmutableBitmap> values,
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
                : values.getOrDefault(value, ImmutableBitmap.empty());
    }

    public ImmutableBitmap getByPrefix(String prefix) {
        Objects.requireNonNull(prefix, "prefix");
        NavigableMap<String, ImmutableBitmap> matches = matchingValues(prefix);
        ImmutableBitmap result = ImmutableBitmap.empty();
        for (ImmutableBitmap bitmap : matches.values()) {
            result = result.or(bitmap);
        }
        return result;
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
            return Optional.of(estimate(matchingValues(prefix.prefix())));
        }
        if (query instanceof EqualQuery<?, ?> equal && equal.field() == field) {
            if (equal.expectedValue() == null) {
                return Optional.empty();
            }
            ImmutableBitmap bitmap = values.get(equal.expectedValue());
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

    TreeMap<String, ImmutableBitmap> copyValues() {
        return new TreeMap<>(values);
    }

    private NavigableMap<String, ImmutableBitmap> matchingValues(String prefix) {
        if (prefix.isEmpty()) {
            return values;
        }
        String upperBound = exclusiveUpperBound(prefix);
        return upperBound == null
                ? values.tailMap(prefix, true)
                : values.subMap(prefix, true, upperBound, false);
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

    private CandidateEstimate estimate(NavigableMap<String, ImmutableBitmap> matches) {
        int cardinality = 0;
        for (ImmutableBitmap bitmap : matches.values()) {
            cardinality = Math.addExact(cardinality, bitmap.cardinality());
        }
        return new CandidateEstimate(
                cardinality,
                matches.size(),
                EstimateQuality.EXACT,
                CandidateAccuracy.EXACT
        );
    }
}
