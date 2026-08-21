package org.example.generalsearch.bitmap;

import java.util.BitSet;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

public final class ImmutableBitmapBuilder {
    private final ImmutableBitmap base;
    private final Map<Integer, BitSet> dirtyBlocks = new HashMap<>();
    private int blockCount;
    private int cardinality;
    private boolean built;

    public ImmutableBitmapBuilder(ImmutableBitmap base) {
        this.base = Objects.requireNonNull(base, "base");
        this.blockCount = base.blockCount();
        this.cardinality = base.cardinality();
    }

    public boolean get(int docId) {
        ensureOpen();
        if (docId < 0) {
            return false;
        }
        int blockIndex = docId / ImmutableBitmap.BLOCK_SIZE;
        BitSet dirty = dirtyBlocks.get(blockIndex);
        return dirty == null ? base.get(docId) : dirty.get(docId % ImmutableBitmap.BLOCK_SIZE);
    }

    public void set(int docId) {
        requireDocId(docId);
        BitSet bits = mutableBlock(docId / ImmutableBitmap.BLOCK_SIZE);
        int offset = docId % ImmutableBitmap.BLOCK_SIZE;
        if (!bits.get(offset)) {
            bits.set(offset);
            cardinality++;
            blockCount = Math.max(blockCount, docId / ImmutableBitmap.BLOCK_SIZE + 1);
        }
    }

    public void clear(int docId) {
        requireDocId(docId);
        if (!get(docId)) {
            return;
        }
        mutableBlock(docId / ImmutableBitmap.BLOCK_SIZE).clear(docId % ImmutableBitmap.BLOCK_SIZE);
        cardinality--;
    }

    public ImmutableBitmap build() {
        ensureOpen();
        PersistentBlockTree<BitBlock> updated = base.blocks();
        for (Map.Entry<Integer, BitSet> entry : dirtyBlocks.entrySet()) {
            BitSet bits = entry.getValue();
            updated = updated.with(
                    entry.getKey(),
                    bits.isEmpty() ? null : BitBlock.fromOwnedBits(bits)
            );
        }
        built = true;
        return new ImmutableBitmap(updated, blockCount, cardinality);
    }

    private BitSet mutableBlock(int blockIndex) {
        ensureOpen();
        return dirtyBlocks.computeIfAbsent(blockIndex, ignored -> {
            BitBlock existing = base.block(blockIndex);
            return existing == null
                    ? new BitSet(ImmutableBitmap.BLOCK_SIZE)
                    : existing.copyBits();
        });
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }

    private void requireDocId(int docId) {
        ensureOpen();
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
    }
}
