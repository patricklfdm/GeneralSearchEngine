package org.example.generalsearch.index.prefix;

import java.util.Objects;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.IndexSnapshot;
import org.example.generalsearch.schema.Field;

public record PrefixIndexDefinition<T>(Field<T, String> field)
        implements IndexDefinition<T> {
    public PrefixIndexDefinition {
        Objects.requireNonNull(field, "field");
    }

    @Override
    public IndexSnapshot<T> createEmpty() {
        return PrefixIndexSnapshot.empty(field);
    }
}
