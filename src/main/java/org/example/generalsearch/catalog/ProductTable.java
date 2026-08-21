package org.example.generalsearch.catalog;

import org.example.generalsearch.bitmap.PersistentBlockTree;
import org.example.generalsearch.model.Product;

public final class ProductTable {
    private final PersistentBlockTree<ProductBlock> blocks;
    private final int blockCount;

    public ProductTable() {
        this(new PersistentBlockTree<>(), 0);
    }

    ProductTable(PersistentBlockTree<ProductBlock> blocks, int blockCount) {
        this.blocks = blocks;
        this.blockCount = blockCount;
    }

    public Product get(int docId) {
        requireDocId(docId);
        ProductBlock block = block(docId / ProductBlock.SIZE);
        return block == null ? null : block.get(docId % ProductBlock.SIZE);
    }

    public ProductTable with(int docId, Product product) {
        requireDocId(docId);
        int blockIndex = docId / ProductBlock.SIZE;
        ProductBlock oldBlock = block(blockIndex);
        ProductBlock newBlock = (oldBlock == null ? ProductBlock.empty() : oldBlock)
                .with(docId % ProductBlock.SIZE, product);
        if (newBlock == oldBlock) {
            return this;
        }
        return new ProductTable(
                blocks.with(blockIndex, newBlock),
                Math.max(blockCount, blockIndex + 1)
        );
    }

    ProductBlock block(int blockIndex) {
        return blockIndex < 0 || blockIndex >= blockCount ? null : blocks.get(blockIndex);
    }

    PersistentBlockTree<ProductBlock> blocks() {
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
