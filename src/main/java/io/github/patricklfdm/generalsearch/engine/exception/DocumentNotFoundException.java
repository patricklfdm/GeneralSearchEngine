package io.github.patricklfdm.generalsearch.engine.exception;

import java.util.Objects;

/** Raised when {@code update} targets a business ID that is not active. */
public final class DocumentNotFoundException extends SearchEngineException {
    private final Object documentId;

    public DocumentNotFoundException(Object documentId) {
        super("document id does not exist: " + Objects.requireNonNull(
                documentId, "documentId"));
        this.documentId = documentId;
    }

    public Object documentId() {
        return documentId;
    }
}
