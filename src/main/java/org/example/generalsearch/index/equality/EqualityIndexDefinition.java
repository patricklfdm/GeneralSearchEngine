package org.example.generalsearch.index.equality;

import java.util.Objects;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.IndexSnapshot;
import org.example.generalsearch.schema.Field;

public record EqualityIndexDefinition<T, V>(Field<T, V> field)
        implements IndexDefinition<T> {
    public EqualityIndexDefinition {
        Objects.requireNonNull(field, "field");
    }

    @Override
    public IndexSnapshot<T> createEmpty() {
        return EqualityIndexSnapshot.empty(field);
    }
}
