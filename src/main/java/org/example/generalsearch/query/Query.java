package org.example.generalsearch.query;

import java.util.List;
import org.example.generalsearch.schema.Field;

@FunctionalInterface
public interface Query<T> {
    boolean matches(T document);

    static <T, V> EqualQuery<T, V> eq(Field<T, V> field, V expectedValue) {
        return new EqualQuery<>(field, expectedValue);
    }

    static <T, V extends Comparable<? super V>> RangeQuery<T, V> between(
            Field<T, V> field,
            V minValue,
            V maxValue
    ) {
        return new RangeQuery<>(field, minValue, maxValue);
    }

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
