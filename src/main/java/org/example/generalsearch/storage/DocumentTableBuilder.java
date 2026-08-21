package org.example.generalsearch.storage;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import org.example.generalsearch.bitmap.PersistentBlockTree;

public final class DocumentTableBuilder<T> {
    private final DocumentTable<T> base;
    private final Map<Integer, Object[]> dirtyBlocks = new HashMap<>();
    private int blockCount;
    private boolean built;

    public DocumentTableBuilder(DocumentTable<T> base) {
        this.base = Objects.requireNonNull(base, "base");
        this.blockCount = base.blockCount();
    }

    @SuppressWarnings("unchecked")
    public T get(int docId) {
        ensureOpen();
        requireDocId(docId);
        int blockIndex = docId / DocumentBlock.SIZE;
        Object[] dirty = dirtyBlocks.get(blockIndex);
        return dirty == null
                ? base.get(docId)
                : (T) dirty[docId % DocumentBlock.SIZE];
    }

    public void set(int docId, T document) {
        ensureOpen();
        requireDocId(docId);
        int blockIndex = docId / DocumentBlock.SIZE;
        Object[] documents = dirtyBlocks.computeIfAbsent(blockIndex, ignored -> {
            DocumentBlock<T> existing = base.block(blockIndex);
            return existing == null
                    ? new Object[DocumentBlock.SIZE]
                    : existing.copyDocuments();
        });
        documents[docId % DocumentBlock.SIZE] = document;
        blockCount = Math.max(blockCount, blockIndex + 1);
    }

    public DocumentTable<T> build() {
        ensureOpen();
        PersistentBlockTree<DocumentBlock<T>> updated = base.blocks();
        for (Map.Entry<Integer, Object[]> entry : dirtyBlocks.entrySet()) {
            updated = updated.with(
                    entry.getKey(),
                    DocumentBlock.owned(entry.getValue())
            );
        }
        built = true;
        return new DocumentTable<>(updated, blockCount);
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }

    private static void requireDocId(int docId) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
    }
}
