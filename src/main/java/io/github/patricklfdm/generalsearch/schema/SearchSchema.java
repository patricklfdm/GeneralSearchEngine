package io.github.patricklfdm.generalsearch.schema;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * Immutable metadata describing a searchable document type and its known fields.
 *
 * @param <T> document type
 * @param <K> non-null business ID type
 */
public final class SearchSchema<T, K> {
    private final Class<T> documentType;
    private final Field<T, K> idField;
    private final Map<String, Field<T, ?>> fields;
    private final Map<String, TextField<T>> textFields;

    private SearchSchema(
            Class<T> documentType,
            Field<T, K> idField,
            Map<String, Field<T, ?>> fields,
            Map<String, TextField<T>> textFields
    ) {
        this.documentType = documentType;
        this.idField = idField;
        this.fields = Collections.unmodifiableMap(new LinkedHashMap<>(fields));
        this.textFields = Collections.unmodifiableMap(new LinkedHashMap<>(textFields));
    }

    public static <T, K> Builder<T, K> builder(
            Class<T> documentType,
            Field<T, K> idField
    ) {
        return new Builder<>(documentType, idField);
    }

    public Class<T> documentType() {
        return documentType;
    }

    public Field<T, K> idField() {
        return idField;
    }

    public K idOf(T document) {
        return Objects.requireNonNull(
                idField.valueOf(document),
                "document id must not be null"
        );
    }

    public Map<String, Field<T, ?>> fields() {
        return fields;
    }

    public Optional<Field<T, ?>> field(String name) {
        Objects.requireNonNull(name, "name");
        return Optional.ofNullable(fields.get(name));
    }

    public Field<T, ?> requireField(String name) {
        return field(name).orElseThrow(
                () -> new IllegalArgumentException("unknown field: " + name));
    }

    @SuppressWarnings("unchecked")
    public <V> Field<T, V> requireField(String name, Class<V> valueType) {
        Objects.requireNonNull(valueType, "valueType");
        Field<T, ?> field = requireField(name);
        if (field.valueType() != valueType) {
            throw new IllegalArgumentException(
                    "field '" + name + "' has type " + field.valueType().getName()
                            + ", not " + valueType.getName());
        }
        return (Field<T, V>) field;
    }

    /** Returns canonical text configurations keyed by their logical field names. */
    public Map<String, TextField<T>> textFields() {
        return textFields;
    }

    /** Returns the canonical text configuration for {@code name}, when registered. */
    public Optional<TextField<T>> textField(String name) {
        Objects.requireNonNull(name, "name");
        return Optional.ofNullable(textFields.get(name));
    }

    /** Returns the canonical text configuration or rejects an unconfigured field. */
    public TextField<T> requireTextField(String name) {
        return textField(name).orElseThrow(
                () -> new IllegalArgumentException("unknown text field: " + name));
    }

    public static final class Builder<T, K> {
        private final Class<T> documentType;
        private final Map<String, Field<T, ?>> fields = new LinkedHashMap<>();
        private final Map<String, TextField<T>> textFields = new LinkedHashMap<>();
        private final Field<T, K> idField;

        private Builder(Class<T> documentType, Field<T, K> idField) {
            this.documentType = Objects.requireNonNull(documentType, "documentType");
            this.idField = Objects.requireNonNull(idField, "idField");
            register(idField);
        }

        public <V> Builder<T, K> field(Field<T, V> field) {
            register(Objects.requireNonNull(field, "field"));
            return this;
        }

        /** Registers one canonical Analyzer configuration for a String field. */
        public Builder<T, K> textField(TextField<T> textField) {
            TextField<T> checked = Objects.requireNonNull(textField, "textField");
            register(checked.field());
            TextField<T> existing = textFields.putIfAbsent(checked.name(), checked);
            if (existing != null && existing != checked) {
                throw new IllegalArgumentException(
                        "duplicate text field name: " + checked.name());
            }
            return this;
        }

        public SearchSchema<T, K> build() {
            return new SearchSchema<>(documentType, idField, fields, textFields);
        }

        private void register(Field<T, ?> field) {
            Field<T, ?> existing = fields.putIfAbsent(field.name(), field);
            if (existing != null && existing != field) {
                throw new IllegalArgumentException(
                        "duplicate field name: " + field.name());
            }
        }
    }
}
