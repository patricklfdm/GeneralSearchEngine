package io.github.patricklfdm.generalsearch.schema;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Locale;
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
                () -> new IllegalArgumentException(unknownFieldMessage(name)));
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
                () -> new IllegalArgumentException(unknownTextFieldMessage(name)));
    }

    private String unknownFieldMessage(String name) {
        StringBuilder message = new StringBuilder("Unknown field '")
                .append(name)
                .append("'.");
        appendSuggestion(message, name, fields.keySet());
        return message.append(" Available fields: ")
                .append(fields.keySet())
                .append('.')
                .toString();
    }

    private String unknownTextFieldMessage(String name) {
        StringBuilder message = new StringBuilder("Text field '")
                .append(name)
                .append("' is not configured.");
        appendSuggestion(message, name, textFields.keySet());
        return message.append(" Configured text fields: ")
                .append(textFields.keySet())
                .append(". Configure one with textIndex(fieldName, analyzer) while ")
                .append("building the engine, or register a TextField explicitly.")
                .toString();
    }

    private static void appendSuggestion(
            StringBuilder message,
            String requested,
            Iterable<String> candidates
    ) {
        String closest = null;
        int closestDistance = Integer.MAX_VALUE;
        for (String candidate : candidates) {
            int distance = editDistance(requested, candidate);
            if (distance < closestDistance) {
                closest = candidate;
                closestDistance = distance;
            }
        }
        int maximumDistance = requested.length() <= 4
                ? 1
                : Math.max(2, requested.length() / 3);
        if (closest != null && closestDistance <= maximumDistance) {
            message.append(" Did you mean '").append(closest).append("'?");
        }
    }

    private static int editDistance(String left, String right) {
        String normalizedLeft = left.toLowerCase(Locale.ROOT);
        String normalizedRight = right.toLowerCase(Locale.ROOT);
        int[] previous = new int[normalizedRight.length() + 1];
        for (int column = 0; column < previous.length; column++) {
            previous[column] = column;
        }
        for (int row = 1; row <= normalizedLeft.length(); row++) {
            int[] current = new int[normalizedRight.length() + 1];
            current[0] = row;
            for (int column = 1; column <= normalizedRight.length(); column++) {
                int substitutionCost = normalizedLeft.charAt(row - 1)
                                == normalizedRight.charAt(column - 1)
                        ? 0
                        : 1;
                current[column] = Math.min(
                        Math.min(current[column - 1] + 1, previous[column] + 1),
                        previous[column - 1] + substitutionCost
                );
            }
            previous = current;
        }
        return previous[normalizedRight.length()];
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
                        "Field '" + field.name() + "' is already registered with a "
                                + "different Field instance. Reuse the canonical field "
                                + "from the schema or generated *SearchFields class.");
            }
        }
    }
}
