package io.github.patricklfdm.generalsearch.engine.exception;

/** Base class for semantic failures reported by an operational search engine. */
public class SearchEngineException extends RuntimeException {
    public SearchEngineException(String message) {
        super(message);
    }

    public SearchEngineException(String message, Throwable cause) {
        super(message, cause);
    }
}
