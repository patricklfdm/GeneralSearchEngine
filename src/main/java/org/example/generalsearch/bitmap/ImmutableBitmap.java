package org.example.generalsearch.bitmap;

import java.util.Objects;
import java.util.function.IntConsumer;

public final class ImmutableBitmap {
    static final int BLOCK_SIZE = 1024;

    private final PersistentBlockTree<BitBlock> blocks;
    private final int blockCount;
    private final int cardinality;

    public ImmutableBitmap() {
        this(new PersistentBlockTree<>(), 0, 0);
    }

    ImmutableBitmap(
            PersistentBlockTree<BitBlock> blocks,
            int blockCount,
            int cardinality
    ) {
        this.blocks = blocks;
        this.blockCount = blockCount;
        this.cardinality = cardinality;
    }

    public static ImmutableBitmap empty() {
        return new ImmutableBitmap();
    }

    public boolean get(int docId) {
        if (docId < 0) {
            return false;
        }
        BitBlock block = block(docId / BLOCK_SIZE);
        return block != null && block.get(docId % BLOCK_SIZE);
    }

    public ImmutableBitmap withSet(int docId) {
        requireDocId(docId);
        if (get(docId)) {
            return this;
        }
        int blockIndex = docId / BLOCK_SIZE;
        int offset = docId % BLOCK_SIZE;
        BitBlock oldBlock = block(blockIndex);
        var bits = oldBlock == null ? new java.util.BitSet(BLOCK_SIZE) : oldBlock.copyBits();
        bits.set(offset);
        return new ImmutableBitmap(
                blocks.with(blockIndex, BitBlock.fromOwnedBits(bits)),
                Math.max(blockCount, blockIndex + 1),
                cardinality + 1
        );
    }

    public ImmutableBitmap withClear(int docId) {
        requireDocId(docId);
        if (!get(docId)) {
            return this;
        }
        int blockIndex = docId / BLOCK_SIZE;
        var bits = Objects.requireNonNull(block(blockIndex)).copyBits();
        bits.clear(docId % BLOCK_SIZE);
        return new ImmutableBitmap(
                blocks.with(blockIndex, bits.isEmpty() ? null : BitBlock.fromOwnedBits(bits)),
                blockCount,
                cardinality - 1
        );
    }

    public ImmutableBitmap and(ImmutableBitmap other) {
        Objects.requireNonNull(other, "other");
        ImmutableBitmapBuilder result = new ImmutableBitmapBuilder(ImmutableBitmap.empty());
        ImmutableBitmap source = cardinality <= other.cardinality ? this : other;
        ImmutableBitmap target = source == this ? other : this;
        source.forEachSetBit(docId -> {
            if (target.get(docId)) {
                result.set(docId);
            }
        });
        return result.build();
    }

    public ImmutableBitmap or(ImmutableBitmap other) {
        Objects.requireNonNull(other, "other");
        if (other.isEmpty()) {
            return this;
        }
        ImmutableBitmapBuilder result = new ImmutableBitmapBuilder(this);
        other.forEachSetBit(result::set);
        return result.build();
    }

    public ImmutableBitmap andNot(ImmutableBitmap other) {
        Objects.requireNonNull(other, "other");
        if (isEmpty() || other.isEmpty()) {
            return this;
        }
        ImmutableBitmapBuilder result = new ImmutableBitmapBuilder(this);
        other.forEachSetBit(result::clear);
        return result.build();
    }

    public void forEachSetBit(IntConsumer consumer) {
        Objects.requireNonNull(consumer, "consumer");
        blocks.forEachPresent((blockIndex, block) ->
                block.forEachSetBit(blockIndex * BLOCK_SIZE, consumer));
    }

    public boolean isEmpty() {
        return cardinality == 0;
    }

    public int cardinality() {
        return cardinality;
    }

    PersistentBlockTree<BitBlock> blocks() {
        return blocks;
    }

    int blockCount() {
        return blockCount;
    }

    BitBlock block(int blockIndex) {
        return blockIndex < 0 || blockIndex >= blockCount ? null : blocks.get(blockIndex);
    }

    private static void requireDocId(int docId) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
    }
}
