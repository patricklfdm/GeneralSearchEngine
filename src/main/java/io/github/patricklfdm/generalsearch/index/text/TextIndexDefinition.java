package io.github.patricklfdm.generalsearch.index.text;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.IndexDefinition;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Defines one inverted index for a canonical schema-owned text field. */
public record TextIndexDefinition<T>(TextField<T> textField)
        implements IndexDefinition<T> {
    public TextIndexDefinition {
        Objects.requireNonNull(textField, "textField");
    }

    @Override
    public Field<T, String> field() {
        return textField.field();
    }

    @Override
    public IndexSnapshot<T> createEmpty() {
        return TextIndexSnapshot.empty(textField);
    }
}
