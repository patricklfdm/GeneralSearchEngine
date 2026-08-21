package io.github.patricklfdm.generalsearch.storage;

final class DocumentBlock<T> {
    static final int SIZE = 1024;

    private final Object[] documents;

    private DocumentBlock(Object[] documents) {
        this.documents = documents;
    }

    static <T> DocumentBlock<T> empty() {
        return new DocumentBlock<>(new Object[SIZE]);
    }

    static <T> DocumentBlock<T> owned(Object[] documents) {
        return new DocumentBlock<>(documents);
    }

    @SuppressWarnings("unchecked")
    T get(int offset) {
        return (T) documents[offset];
    }

    DocumentBlock<T> with(int offset, T document) {
        if (documents[offset] == document) {
            return this;
        }
        Object[] copy = documents.clone();
        copy[offset] = document;
        return new DocumentBlock<>(copy);
    }

    Object[] copyDocuments() {
        return documents.clone();
    }
}
