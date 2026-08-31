package io.github.patricklfdm.generalsearch.search;

/**
 * Opaque continuation marker returned by a paged-search implementation.
 *
 * <p>Applications may retain a cursor and pass it back to the engine that created it,
 * but must not assume a representation, equality contract, portability, or validity
 * after the engine publishes another snapshot.</p>
 */
public interface SearchAfterCursor {
}
