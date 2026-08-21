package io.github.patricklfdm.generalsearch.index.equality;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;

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
