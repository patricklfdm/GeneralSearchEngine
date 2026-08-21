package io.github.patricklfdm.generalsearch.index;

/**
 * Single-use mutation view used to derive a new immutable index snapshot.
 *
 * @param <T> indexed document type
 */
public interface IndexBuilder<T> {
    /** Adds the document's field value for an internal document ID. */
    void add(int docId, T document);

    /** Removes the document's field value for an internal document ID. */
    void remove(int docId, T document);

    /** Replaces the indexed value associated with an internal document ID. */
    void update(int docId, T oldDocument, T newDocument);

    /** Publishes the derived immutable snapshot and closes this builder. */
    IndexSnapshot<T> build();
}
