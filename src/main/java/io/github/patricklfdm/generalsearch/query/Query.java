package io.github.patricklfdm.generalsearch.query;

import java.util.List;
import io.github.patricklfdm.generalsearch.schema.Field;

/**
 * Predicate evaluated against documents after optional index-based candidate planning.
 *
 * @param <T> queried document type
 */
@FunctionalInterface
public interface Query<T> {
    /** Returns whether one non-null document satisfies this query. */
    boolean matches(T document);

    /** Uses {@link java.util.Objects#equals(Object, Object)}; null is a valid value. */
    static <T, V> EqualQuery<T, V> eq(Field<T, V> field, V expectedValue) {
        return new EqualQuery<>(field, expectedValue);
    }

    /** Creates an inclusive range using the value type's natural ordering. */
    static <T, V extends Comparable<? super V>> RangeQuery<T, V> between(
            Field<T, V> field,
            V minValue,
            V maxValue
    ) {
        return new RangeQuery<>(field, minValue, maxValue);
    }

    /** Uses case-sensitive {@link String#startsWith(String)} semantics. */
    static <T> PrefixQuery<T> prefix(Field<T, String> field, String prefix) {
        return new PrefixQuery<>(field, prefix);
    }

    @SafeVarargs
    static <T> AndQuery<T> and(Query<T>... queries) {
        return new AndQuery<>(List.of(queries));
    }

    static <T> AndQuery<T> and(List<? extends Query<T>> queries) {
        return new AndQuery<>(List.copyOf(queries));
    }

    @SafeVarargs
    static <T> OrQuery<T> or(Query<T>... queries) {
        return new OrQuery<>(List.of(queries));
    }

    static <T> OrQuery<T> or(List<? extends Query<T>> queries) {
        return new OrQuery<>(List.copyOf(queries));
    }

    static <T> NotQuery<T> not(Query<T> query) {
        return new NotQuery<>(query);
    }

    static <T> MatchAllQuery<T> matchAll() {
        return new MatchAllQuery<>();
    }
}
