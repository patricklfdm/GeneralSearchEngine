package org.example.generalsearch.bitmap;

import java.util.BitSet;
import java.util.function.IntConsumer;

public final class BitBlock {
    private final BitSet bits;

    private BitBlock(BitSet bits) {
        this.bits = bits;
    }

    static BitBlock fromOwnedBits(BitSet bits) {
        return new BitBlock(bits);
    }

    static BitBlock single(int offset) {
        BitSet bits = new BitSet(ImmutableBitmap.BLOCK_SIZE);
        bits.set(offset);
        return new BitBlock(bits);
    }

    boolean get(int offset) {
        return bits.get(offset);
    }

    BitSet copyBits() {
        return (BitSet) bits.clone();
    }

    void forEachSetBit(int baseDocId, IntConsumer consumer) {
        for (int offset = bits.nextSetBit(0); offset >= 0; offset = bits.nextSetBit(offset + 1)) {
            consumer.accept(baseDocId + offset);
        }
    }
}
