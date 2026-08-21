package io.github.patricklfdm.generalsearch.schema;

public final class SchemaGenerationException extends IllegalArgumentException {
    public SchemaGenerationException(String message) {
        super(message);
    }

    public SchemaGenerationException(String message, Throwable cause) {
        super(message, cause);
    }
}
