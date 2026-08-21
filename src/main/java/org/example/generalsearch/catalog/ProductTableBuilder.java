package org.example.generalsearch.catalog;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import org.example.generalsearch.bitmap.PersistentBlockTree;
import org.example.generalsearch.model.Product;

public final class ProductTableBuilder {
    private final ProductTable base;
    private final Map<Integer, Product[]> dirtyBlocks = new HashMap<>();
    private int blockCount;
    private boolean built;

    public ProductTableBuilder(ProductTable base) {
        this.base = Objects.requireNonNull(base, "base");
        this.blockCount = base.blockCount();
    }

    public Product get(int docId) {
        ensureOpen();
        requireDocId(docId);
        int blockIndex = docId / ProductBlock.SIZE;
        Product[] dirty = dirtyBlocks.get(blockIndex);
        return dirty == null ? base.get(docId) : dirty[docId % ProductBlock.SIZE];
    }

    public void set(int docId, Product product) {
        ensureOpen();
        requireDocId(docId);
        int blockIndex = docId / ProductBlock.SIZE;
        Product[] products = dirtyBlocks.computeIfAbsent(blockIndex, ignored -> {
            ProductBlock existing = base.block(blockIndex);
            return existing == null ? new Product[ProductBlock.SIZE] : existing.copyProducts();
        });
        products[docId % ProductBlock.SIZE] = product;
        blockCount = Math.max(blockCount, blockIndex + 1);
    }

    public ProductTable build() {
        ensureOpen();
        PersistentBlockTree<ProductBlock> updated = base.blocks();
        for (Map.Entry<Integer, Product[]> entry : dirtyBlocks.entrySet()) {
            updated = updated.with(entry.getKey(), ProductBlock.owned(entry.getValue()));
        }
        built = true;
        return new ProductTable(updated, blockCount);
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
