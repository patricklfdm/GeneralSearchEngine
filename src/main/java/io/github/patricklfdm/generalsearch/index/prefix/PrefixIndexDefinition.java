package io.github.patricklfdm.generalsearch.index.prefix;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;

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
