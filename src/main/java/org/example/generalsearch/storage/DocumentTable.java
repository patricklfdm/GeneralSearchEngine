package org.example.generalsearch.storage;

import org.example.generalsearch.bitmap.PersistentBlockTree;

public final class DocumentTable<T> {
    private final PersistentBlockTree<DocumentBlock<T>> blocks;
    private final int blockCount;

    public DocumentTable() {
        this(new PersistentBlockTree<>(), 0);
    }

    DocumentTable(PersistentBlockTree<DocumentBlock<T>> blocks, int blockCount) {
        this.blocks = blocks;
        this.blockCount = blockCount;
    }

    public T get(int docId) {
        requireDocId(docId);
        DocumentBlock<T> block = block(docId / DocumentBlock.SIZE);
        return block == null ? null : block.get(docId % DocumentBlock.SIZE);
    }

    public DocumentTable<T> with(int docId, T document) {
        requireDocId(docId);
        int blockIndex = docId / DocumentBlock.SIZE;
        DocumentBlock<T> oldBlock = block(blockIndex);
        DocumentBlock<T> newBlock = (oldBlock == null
                ? DocumentBlock.<T>empty()
                : oldBlock).with(docId % DocumentBlock.SIZE, document);
        if (newBlock == oldBlock) {
            return this;
        }
        return new DocumentTable<>(
                blocks.with(blockIndex, newBlock),
                Math.max(blockCount, blockIndex + 1)
        );
    }

    DocumentBlock<T> block(int blockIndex) {
        return blockIndex < 0 || blockIndex >= blockCount ? null : blocks.get(blockIndex);
    }

    PersistentBlockTree<DocumentBlock<T>> blocks() {
        return blocks;
    }

    int blockCount() {
        return blockCount;
    }

    private static void requireDocId(int docId) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
    }
}
