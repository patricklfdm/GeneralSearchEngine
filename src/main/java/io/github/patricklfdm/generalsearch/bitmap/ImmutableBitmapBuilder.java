package io.github.patricklfdm.generalsearch.bitmap;

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
        if (get(docId)) {
            return;
        }
        BitSet bits = mutableBlock(docId / ImmutableBitmap.BLOCK_SIZE);
        int offset = docId % ImmutableBitmap.BLOCK_SIZE;
        bits.set(offset);
        cardinality++;
        blockCount = Math.max(blockCount, docId / ImmutableBitmap.BLOCK_SIZE + 1);
    }

    public void clear(int docId) {
        requireDocId(docId);
        if (!get(docId)) {
            return;
        }
        mutableBlock(docId / ImmutableBitmap.BLOCK_SIZE).clear(docId % ImmutableBitmap.BLOCK_SIZE);
        cardinality--;
    }

    /**
     * Adds every document from {@code other} to this builder.
     *
     * <p>The operation merges complete bitmap blocks and leaves freezing to
     * {@link #build()}, allowing callers to accumulate many sources without creating
     * an immutable intermediate for every source.</p>
     *
     * @param other bitmap whose documents are added
     */
    public void or(ImmutableBitmap other) {
        ensureOpen();
        Objects.requireNonNull(other, "other");
        if (other.isEmpty() || (other == base && dirtyBlocks.isEmpty())) {
            return;
        }
        other.blocks().forEachPresent((blockIndex, block) -> {
            BitSet bits = mutableBlock(blockIndex);
            int previousCardinality = bits.cardinality();
            block.orInto(bits);
            cardinality += bits.cardinality() - previousCardinality;
            blockCount = Math.max(blockCount, blockIndex + 1);
        });
    }

    public ImmutableBitmap build() {
        ensureOpen();
        if (dirtyBlocks.isEmpty()) {
            built = true;
            return base;
        }
        PersistentBlockTree<BitBlock> updated = base.blocks();
        boolean changed = false;
        for (Map.Entry<Integer, BitSet> entry : dirtyBlocks.entrySet()) {
            BitSet bits = entry.getValue();
            BitBlock existing = base.block(entry.getKey());
            if (existing == null ? bits.isEmpty() : existing.hasSameBits(bits)) {
                continue;
            }
            updated = updated.with(
                    entry.getKey(),
                    bits.isEmpty() ? null : BitBlock.fromOwnedBits(bits)
            );
            changed = true;
        }
        built = true;
        if (!changed) {
            return base;
        }
        return new ImmutableBitmap(updated, blockCount, cardinality);
    }

    private BitSet mutableBlock(int blockIndex) {
        ensureOpen();
        BitSet dirty = dirtyBlocks.get(blockIndex);
        if (dirty != null) {
            return dirty;
        }
        BitBlock existing = base.block(blockIndex);
        BitSet created = existing == null
                ? new BitSet(ImmutableBitmap.BLOCK_SIZE)
                : existing.copyBits();
        dirtyBlocks.put(blockIndex, created);
        return created;
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
