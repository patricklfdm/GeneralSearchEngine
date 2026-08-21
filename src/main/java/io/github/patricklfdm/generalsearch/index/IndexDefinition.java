package io.github.patricklfdm.generalsearch.index;

import io.github.patricklfdm.generalsearch.index.equality.EqualityIndexDefinition;
import io.github.patricklfdm.generalsearch.index.prefix.PrefixIndexDefinition;
import io.github.patricklfdm.generalsearch.index.range.RangeIndexDefinition;
import io.github.patricklfdm.generalsearch.schema.Field;

/**
 * Reusable definition that creates an empty immutable index snapshot.
 *
 * <p>Custom index implementations form the v1 extension SPI together with
 * {@link IndexSnapshot} and {@link IndexBuilder}. Implementations must return snapshots
 * for the exact same canonical {@link Field} instance.</p>
 *
 * @param <T> indexed document type
 */
public interface IndexDefinition<T> {
    /** Returns the canonical schema field indexed by this definition. */
    Field<T, ?> field();

    /** Creates an empty snapshot that can produce an incremental builder. */
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
