package org.example.generalsearch.index;

public interface IndexBuilder<T> {
    void add(int docId, T document);

    void remove(int docId, T document);

    void update(int docId, T oldDocument, T newDocument);

    IndexSnapshot<T> build();
}
