package org.example.generalsearch.bitmap;

final class BlockTreeNode {
    static final int BRANCHING = 32;

    final Object[] children;

    private BlockTreeNode(Object[] children) {
        this.children = children;
    }

    static BlockTreeNode empty() {
        return new BlockTreeNode(new Object[BRANCHING]);
    }

    static BlockTreeNode owned(Object[] children) {
        return new BlockTreeNode(children);
    }
}
