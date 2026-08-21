package org.example.generalsearch.index;

import org.example.generalsearch.index.equality.EqualityIndexDefinition;
import org.example.generalsearch.index.prefix.PrefixIndexDefinition;
import org.example.generalsearch.index.range.RangeIndexDefinition;
import org.example.generalsearch.schema.Field;

public interface IndexDefinition<T> {
    Field<T, ?> field();

    IndexSnapshot<T> createEmpty();

    static <T, V> EqualityIndexDefinition<T, V> equality(Field<T, V> field) {
        return new EqualityIndexDefinition<>(field);
    }

    static <T, V extends Comparable<? super V>> RangeIndexDefinition<T, V> range(
            Field<T, V> field
    ) {
        return new RangeIndexDefinition<>(field);
    }

    static <T> PrefixIndexDefinition<T> prefix(Field<T, String> field) {
        return new PrefixIndexDefinition<>(field);
    }
}
