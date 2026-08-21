package org.example.generalsearch.index.prefix;

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
import org.example.generalsearch.query.PrefixQuery;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.schema.Field;

public final class PrefixIndexSnapshot<T> implements IndexSnapshot<T> {
    private final Field<T, String> field;
    private final NavigableMap<String, ImmutableBitmap> values;

    private PrefixIndexSnapshot(
            Field<T, String> field,
            NavigableMap<String, ImmutableBitmap> values
    ) {
        this.field = Objects.requireNonNull(field, "field");
        this.values = Collections.unmodifiableNavigableMap(new TreeMap<>(values));
    }

    public static <T> PrefixIndexSnapshot<T> empty(Field<T, String> field) {
        return new PrefixIndexSnapshot<>(field, new TreeMap<>());
    }

    static <T> PrefixIndexSnapshot<T> fromOwnedValues(
            Field<T, String> field,
            NavigableMap<String, ImmutableBitmap> values
    ) {
        return new PrefixIndexSnapshot<>(field, values);
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
}
