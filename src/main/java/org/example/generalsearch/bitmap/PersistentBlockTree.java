package org.example.generalsearch.bitmap;

import java.util.Objects;
import java.util.function.BiConsumer;

public final class PersistentBlockTree<T> {
    private static final int BITS = 5;
    private static final int MASK = BlockTreeNode.BRANCHING - 1;

    private final BlockTreeNode root;
    private final int shift;

    public PersistentBlockTree() {
        this(BlockTreeNode.empty(), 0);
    }

    private PersistentBlockTree(BlockTreeNode root, int shift) {
        this.root = root;
        this.shift = shift;
    }

    @SuppressWarnings("unchecked")
    public T get(int index) {
        requireIndex(index);
        if (index >= capacityForShift(shift)) {
            return null;
        }

        BlockTreeNode node = root;
        for (int currentShift = shift; currentShift > 0; currentShift -= BITS) {
            Object child = node.children[(index >>> currentShift) & MASK];
            if (child == null) {
                return null;
            }
            node = (BlockTreeNode) child;
        }
        return (T) node.children[index & MASK];
    }

    public PersistentBlockTree<T> with(int index, T value) {
        requireIndex(index);
        BlockTreeNode expandedRoot = root;
        int expandedShift = shift;
        while (index >= capacityForShift(expandedShift)) {
            Object[] children = new Object[BlockTreeNode.BRANCHING];
            children[0] = expandedRoot;
            expandedRoot = BlockTreeNode.owned(children);
            expandedShift += BITS;
        }

        BlockTreeNode updatedRoot = associate(expandedRoot, expandedShift, index, value);
        if (updatedRoot == root && expandedShift == shift) {
            return this;
        }
        return new PersistentBlockTree<>(updatedRoot, expandedShift);
    }

    public void forEachPresent(BiConsumer<Integer, T> consumer) {
        Objects.requireNonNull(consumer, "consumer");
        forEachPresent(root, shift, 0, consumer);
    }

    public boolean isEmpty() {
        return isEmpty(root, shift);
    }

    private BlockTreeNode associate(BlockTreeNode node, int currentShift, int index, T value) {
        int slot = (index >>> currentShift) & MASK;
        if (currentShift == 0) {
            if (node.children[slot] == value) {
                return node;
            }
            Object[] children = node.children.clone();
            children[slot] = value;
            return BlockTreeNode.owned(children);
        }

        BlockTreeNode oldChild = (BlockTreeNode) node.children[slot];
        BlockTreeNode newChild = oldChild == null
                ? newPath(currentShift - BITS, index, value)
                : associate(oldChild, currentShift - BITS, index, value);
        if (newChild == oldChild) {
            return node;
        }
        Object[] children = node.children.clone();
        children[slot] = newChild;
        return BlockTreeNode.owned(children);
    }

    private BlockTreeNode newPath(int currentShift, int index, T value) {
        Object[] children = new Object[BlockTreeNode.BRANCHING];
        int slot = (index >>> currentShift) & MASK;
        children[slot] = currentShift == 0
                ? value
                : newPath(currentShift - BITS, index, value);
        return BlockTreeNode.owned(children);
    }

    @SuppressWarnings("unchecked")
    private void forEachPresent(
            BlockTreeNode node,
            int currentShift,
            int prefix,
            BiConsumer<Integer, T> consumer
    ) {
        if (currentShift == 0) {
            for (int slot = 0; slot < BlockTreeNode.BRANCHING; slot++) {
                Object value = node.children[slot];
                if (value != null) {
                    consumer.accept(prefix | slot, (T) value);
                }
            }
            return;
        }

        for (int slot = 0; slot < BlockTreeNode.BRANCHING; slot++) {
            Object child = node.children[slot];
            if (child != null) {
                forEachPresent(
                        (BlockTreeNode) child,
                        currentShift - BITS,
                        prefix | (slot << currentShift),
                        consumer
                );
            }
        }
    }

    private boolean isEmpty(BlockTreeNode node, int currentShift) {
        for (Object child : node.children) {
            if (child == null) {
                continue;
            }
            if (currentShift == 0 || !isEmpty((BlockTreeNode) child, currentShift - BITS)) {
                return false;
            }
        }
        return true;
    }

    private static long capacityForShift(int shift) {
        return 1L << (shift + BITS);
    }

    private static void requireIndex(int index) {
        if (index < 0) {
            throw new IndexOutOfBoundsException("index must not be negative");
        }
    }
}
