package io.github.patricklfdm.generalsearch.index.range;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;

public record RangeIndexDefinition<T, V extends Comparable<? super V>>(Field<T, V> field)
        implements IndexDefinition<T> {
    public RangeIndexDefinition {
        Objects.requireNonNull(field, "field");
    }

    @Override
    public IndexSnapshot<T> createEmpty() {
        return RangeIndexSnapshot.empty(field);
    }
}
