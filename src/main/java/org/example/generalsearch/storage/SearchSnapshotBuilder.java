package org.example.generalsearch.storage;

import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmapBuilder;
import org.example.generalsearch.index.IndexRegistryBuilder;

public final class SearchSnapshotBuilder<T> {
    private final DocumentTableBuilder<T> documents;
    private final ImmutableBitmapBuilder activeDocuments;
    private final IndexRegistryBuilder<T> indexes;
    private boolean built;

    public SearchSnapshotBuilder(SearchSnapshot<T> base) {
        Objects.requireNonNull(base, "base");
        this.documents = new DocumentTableBuilder<>(base.documents());
        this.activeDocuments = new ImmutableBitmapBuilder(base.activeDocuments());
        this.indexes = base.indexes().toBuilder();
    }

    public void add(int docId, T document) {
        ensureOpen();
        Objects.requireNonNull(document, "document");
        if (activeDocuments.get(docId)) {
            throw new IllegalStateException("docId is already active: " + docId);
        }
        documents.set(docId, document);
        activeDocuments.set(docId);
        indexes.add(docId, document);
    }

    public void update(int docId, T document) {
        ensureOpen();
        Objects.requireNonNull(document, "document");
        T oldDocument = requireActiveDocument(docId);
        documents.set(docId, document);
        indexes.update(docId, oldDocument, document);
    }

    public void remove(int docId) {
        ensureOpen();
        if (!activeDocuments.get(docId)) {
            return;
        }
        T document = requireActiveDocument(docId);
        indexes.remove(docId, document);
        documents.set(docId, null);
        activeDocuments.clear(docId);
    }

    public SearchSnapshot<T> build() {
        ensureOpen();
        built = true;
        return new SearchSnapshot<>(
                documents.build(),
                activeDocuments.build(),
                indexes.build()
        );
    }

    private T requireActiveDocument(int docId) {
        if (!activeDocuments.get(docId)) {
            throw new IllegalStateException("docId is not active: " + docId);
        }
        T document = documents.get(docId);
        if (document == null) {
            throw new IllegalStateException("active docId has no document: " + docId);
        }
        return document;
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
