package org.example.generalsearch.schema;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * Immutable metadata describing a searchable document type and its known fields.
 */
public final class SearchSchema<T> {
    private final Class<T> documentType;
    private final Field<T, ?> idField;
    private final Map<String, Field<T, ?>> fields;

    private SearchSchema(
            Class<T> documentType,
            Field<T, ?> idField,
            Map<String, Field<T, ?>> fields
    ) {
        this.documentType = documentType;
        this.idField = idField;
        this.fields = Collections.unmodifiableMap(new LinkedHashMap<>(fields));
    }

    public static <T> Builder<T> builder(Class<T> documentType) {
        return new Builder<>(documentType);
    }

    public Class<T> documentType() {
        return documentType;
    }

    public Field<T, ?> idField() {
        return idField;
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

    public static final class Builder<T> {
        private final Class<T> documentType;
        private final Map<String, Field<T, ?>> fields = new LinkedHashMap<>();
        private Field<T, ?> idField;

        private Builder(Class<T> documentType) {
            this.documentType = Objects.requireNonNull(documentType, "documentType");
        }

        public <V> Builder<T> id(Field<T, V> field) {
            Objects.requireNonNull(field, "field");
            if (idField != null && idField != field) {
                throw new IllegalStateException("id field has already been configured");
            }
            idField = field;
            register(field);
            return this;
        }

        public <V> Builder<T> field(Field<T, V> field) {
            register(Objects.requireNonNull(field, "field"));
            return this;
        }

        public SearchSchema<T> build() {
            if (idField == null) {
                throw new IllegalStateException("an id field is required");
            }
            return new SearchSchema<>(documentType, idField, fields);
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
