package org.example.generalsearch.index.range;

import java.util.Objects;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.IndexSnapshot;
import org.example.generalsearch.schema.Field;

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
