package org.example.generalsearch.schema;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * Immutable metadata describing a searchable document type and its known fields.
 */
public final class SearchSchema<T, K> {
    private final Class<T> documentType;
    private final Field<T, K> idField;
    private final Map<String, Field<T, ?>> fields;

    private SearchSchema(
            Class<T> documentType,
            Field<T, K> idField,
            Map<String, Field<T, ?>> fields
    ) {
        this.documentType = documentType;
        this.idField = idField;
        this.fields = Collections.unmodifiableMap(new LinkedHashMap<>(fields));
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

    public static final class Builder<T, K> {
        private final Class<T> documentType;
        private final Map<String, Field<T, ?>> fields = new LinkedHashMap<>();
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

        public SearchSchema<T, K> build() {
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
