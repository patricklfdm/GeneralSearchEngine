package io.github.patricklfdm.generalsearch.engine.exception;

import java.util.Objects;

/** Raised when {@code add} receives a business ID that is already active. */
public final class DocumentAlreadyExistsException extends SearchEngineException {
    private final Object documentId;

    public DocumentAlreadyExistsException(Object documentId) {
        super("document id already exists: " + Objects.requireNonNull(
                documentId, "documentId"));
        this.documentId = documentId;
    }

    public Object documentId() {
        return documentId;
    }
}
