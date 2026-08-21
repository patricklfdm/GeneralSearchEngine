package org.example.generalsearch.storage;

import java.util.Collection;
import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.IndexRegistry;

public final class SearchSnapshot<T> {
    private final DocumentTable<T> documents;
    private final ImmutableBitmap activeDocuments;
    private final IndexRegistry<T> indexes;
    private final long version;

    public SearchSnapshot(Collection<? extends IndexDefinition<T>> definitions) {
        this(
                new DocumentTable<>(),
                ImmutableBitmap.empty(),
                IndexRegistry.create(definitions),
                0
        );
    }

    SearchSnapshot(
            DocumentTable<T> documents,
            ImmutableBitmap activeDocuments,
            IndexRegistry<T> indexes,
            long version
    ) {
        this.documents = Objects.requireNonNull(documents, "documents");
        this.activeDocuments = Objects.requireNonNull(activeDocuments, "activeDocuments");
        this.indexes = Objects.requireNonNull(indexes, "indexes");
        if (version < 0) {
            throw new IllegalArgumentException("version must not be negative");
        }
        this.version = version;
    }

    public T get(int docId) {
        return activeDocuments.get(docId) ? documents.get(docId) : null;
    }

    public SearchSnapshot<T> add(int docId, T document) {
        SearchSnapshotBuilder<T> builder = new SearchSnapshotBuilder<>(this);
        builder.add(docId, document);
        return builder.build();
    }

    public SearchSnapshot<T> update(int docId, T document) {
        SearchSnapshotBuilder<T> builder = new SearchSnapshotBuilder<>(this);
        builder.update(docId, document);
        return builder.build();
    }

    public SearchSnapshot<T> remove(int docId) {
        SearchSnapshotBuilder<T> builder = new SearchSnapshotBuilder<>(this);
        builder.remove(docId);
        return builder.build();
    }

    public DocumentTable<T> documents() {
        return documents;
    }

    public ImmutableBitmap activeDocuments() {
        return activeDocuments;
    }

    public IndexRegistry<T> indexes() {
        return indexes;
    }

    public long version() {
        return version;
    }

    public SearchSnapshot<T> withIndexes(IndexRegistry<T> newIndexes) {
        Objects.requireNonNull(newIndexes, "newIndexes");
        if (newIndexes == indexes) {
            return this;
        }
        return new SearchSnapshot<>(
                documents,
                activeDocuments,
                newIndexes,
                Math.addExact(version, 1)
        );
    }
}
