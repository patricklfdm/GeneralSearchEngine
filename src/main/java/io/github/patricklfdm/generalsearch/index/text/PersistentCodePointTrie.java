package io.github.patricklfdm.generalsearch.index.text;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.BiConsumer;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;

/** Immutable normalized-term trie with path-copying updates. */
final class PersistentCodePointTrie {
    private static final int MAX_EDITS = 2;

    private final Node root;
    private final int size;

    private PersistentCodePointTrie(Node root, int size) {
        this.root = root;
        this.size = size;
    }

    static PersistentCodePointTrie empty() {
        return new PersistentCodePointTrie(null, 0);
    }

    int size() {
        return size;
    }

    PersistentCodePointTrie with(String term) {
        int[] codePoints = codePoints(term);
        if (find(root, codePoints, 0) != null) {
            return this;
        }
        return new PersistentCodePointTrie(
                put(root, codePoints, 0, term),
                Math.addExact(size, 1)
        );
    }

    PersistentCodePointTrie without(String term) {
        int[] codePoints = codePoints(term);
        if (find(root, codePoints, 0) == null) {
            return this;
        }
        return new PersistentCodePointTrie(
                remove(root, codePoints, 0),
                size - 1
        );
    }

    PersistentCodePointTrie withMembershipChanges(
            Map<String, Boolean> membershipByTerm
    ) {
        Objects.requireNonNull(membershipByTerm, "membershipByTerm");
        if (membershipByTerm.isEmpty()) {
            return this;
        }
        if (membershipByTerm.size() <= 2) {
            PersistentCodePointTrie updated = this;
            for (var change : membershipByTerm.entrySet()) {
                updated = change.getValue()
                        ? updated.with(change.getKey())
                        : updated.without(change.getKey());
            }
            return updated;
        }

        List<MembershipChange> changes = new ArrayList<>(membershipByTerm.size());
        int updatedSize = size;
        for (var entry : membershipByTerm.entrySet()) {
            String term = Objects.requireNonNull(entry.getKey(), "term");
            boolean present = Objects.requireNonNull(entry.getValue(), "present");
            int[] points = codePoints(term);
            boolean currentlyPresent = find(root, points, 0) != null;
            if (currentlyPresent == present) {
                continue;
            }
            changes.add(new MembershipChange(term, points, present));
            updatedSize = present
                    ? Math.addExact(updatedSize, 1)
                    : Math.subtractExact(updatedSize, 1);
        }
        if (changes.isEmpty()) {
            return this;
        }
        changes.sort(MembershipChange.ORDER);
        return new PersistentCodePointTrie(
                update(root, changes, 0, changes.size(), 0),
                updatedSize
        );
    }

    void forEachWithinEditDistance(
            String queryTerm,
            int maxEdits,
            BiConsumer<? super String, ? super Integer> consumer
    ) {
        int[] queryPoints = codePoints(queryTerm);
        if (maxEdits < 0 || maxEdits > MAX_EDITS) {
            throw new IllegalArgumentException("maxEdits must be between 0 and 2");
        }
        Objects.requireNonNull(consumer, "consumer");
        if (root == null) {
            return;
        }

        TraversalWorkspace workspace = new TraversalWorkspace(queryPoints.length + 1);
        int[] initial = workspace.row(0);
        int sentinel = maxEdits + 1;
        for (int column = 0; column < initial.length; column++) {
            initial[column] = Math.min(column, sentinel);
        }
        root.children.forEachInRange(
                null,
                true,
                null,
                true,
                (codePoint, child) -> visit(
                        child,
                        codePoint,
                        1,
                        -1,
                        queryPoints,
                        maxEdits,
                        workspace,
                        consumer
                )
        );
    }

    Node nodeForPrefix(String prefix) {
        Objects.requireNonNull(prefix, "prefix");
        int[] points = prefix.codePoints().toArray();
        Node node = root;
        for (int point : points) {
            if (node == null) {
                return null;
            }
            node = node.children.get(point);
        }
        return node;
    }

    private static void visit(
            Node node,
            int codePoint,
            int depth,
            int previousCodePoint,
            int[] queryPoints,
            int maxEdits,
            TraversalWorkspace workspace,
            BiConsumer<? super String, ? super Integer> consumer
    ) {
        int sentinel = maxEdits + 1;
        int[] previous = workspace.row(depth - 1);
        int[] current = workspace.row(depth);
        Arrays.fill(current, sentinel);
        current[0] = Math.min(depth, sentinel);

        int firstColumn = Math.max(1, depth - maxEdits);
        int lastColumn = Math.min(queryPoints.length, depth + maxEdits);
        int rowMinimum = current[0];
        for (int column = firstColumn; column <= lastColumn; column++) {
            int deletion = increment(previous[column], sentinel);
            int insertion = increment(current[column - 1], sentinel);
            int substitution = previous[column - 1] >= sentinel
                    ? sentinel
                    : previous[column - 1]
                            + (codePoint == queryPoints[column - 1] ? 0 : 1);
            int best = Math.min(deletion, Math.min(insertion, substitution));

            if (depth > 1
                    && column > 1
                    && codePoint == queryPoints[column - 2]
                    && previousCodePoint == queryPoints[column - 1]) {
                best = Math.min(
                        best,
                        increment(workspace.row(depth - 2)[column - 2], sentinel)
                );
            }
            current[column] = Math.min(best, sentinel);
            rowMinimum = Math.min(rowMinimum, current[column]);
        }

        int distance = current[queryPoints.length];
        if (node.terminal != null && distance <= maxEdits) {
            consumer.accept(node.terminal, distance);
        }
        if (rowMinimum > maxEdits) {
            return;
        }
        node.children.forEachInRange(
                null,
                true,
                null,
                true,
                (childPoint, child) -> visit(
                        child,
                        childPoint,
                        Math.addExact(depth, 1),
                        codePoint,
                        queryPoints,
                        maxEdits,
                        workspace,
                        consumer
                )
        );
    }

    private static Node put(
            Node node,
            int[] codePoints,
            int index,
            String term
    ) {
        Node current = node == null ? Node.empty() : node;
        if (index == codePoints.length) {
            return new Node(term, current.children);
        }
        int codePoint = codePoints[index];
        Node child = current.children.get(codePoint);
        Node updatedChild = put(child, codePoints, index + 1, term);
        return new Node(
                current.terminal,
                current.children.with(codePoint, updatedChild)
        );
    }

    private static Node update(
            Node node,
            List<MembershipChange> changes,
            int fromIndex,
            int toIndex,
            int depth
    ) {
        Node current = node == null ? Node.empty() : node;
        String terminal = current.terminal;
        PersistentAvlMap<Integer, Node> children = current.children;
        int index = fromIndex;
        if (changes.get(index).codePoints.length == depth) {
            MembershipChange terminalChange = changes.get(index++);
            terminal = terminalChange.present ? terminalChange.term : null;
        }

        while (index < toIndex) {
            int codePoint = changes.get(index).codePoints[depth];
            int groupEnd = index + 1;
            while (groupEnd < toIndex
                    && changes.get(groupEnd).codePoints[depth] == codePoint) {
                groupEnd++;
            }
            Node updatedChild = update(
                    children.get(codePoint),
                    changes,
                    index,
                    groupEnd,
                    depth + 1
            );
            children = updatedChild == null
                    ? children.without(codePoint)
                    : children.with(codePoint, updatedChild);
            index = groupEnd;
        }

        if (terminal == null && children.size() == 0) {
            return null;
        }
        if (node != null
                && Objects.equals(terminal, node.terminal)
                && children == node.children) {
            return node;
        }
        return new Node(terminal, children);
    }

    private static Node remove(Node node, int[] codePoints, int index) {
        if (index == codePoints.length) {
            return node.children.size() == 0
                    ? null
                    : new Node(null, node.children);
        }
        int codePoint = codePoints[index];
        Node child = node.children.get(codePoint);
        Node updatedChild = remove(child, codePoints, index + 1);
        PersistentAvlMap<Integer, Node> updatedChildren = updatedChild == null
                ? node.children.without(codePoint)
                : node.children.with(codePoint, updatedChild);
        if (node.terminal == null && updatedChildren.size() == 0) {
            return null;
        }
        return new Node(node.terminal, updatedChildren);
    }

    private static String find(Node node, int[] codePoints, int index) {
        Node current = node;
        for (int offset = index; offset < codePoints.length; offset++) {
            if (current == null) {
                return null;
            }
            current = current.children.get(codePoints[offset]);
        }
        return current == null ? null : current.terminal;
    }

    private static int[] codePoints(String term) {
        Objects.requireNonNull(term, "term");
        if (term.isEmpty()) {
            throw new IllegalArgumentException("term must not be empty");
        }
        return term.codePoints().toArray();
    }

    private static int increment(int value, int sentinel) {
        return value >= sentinel ? sentinel : value + 1;
    }

    private record MembershipChange(
            String term,
            int[] codePoints,
            boolean present
    ) {
        private static final Comparator<MembershipChange> ORDER = (left, right) -> {
            int sharedLength = Math.min(
                    left.codePoints.length,
                    right.codePoints.length
            );
            for (int index = 0; index < sharedLength; index++) {
                int comparison = Integer.compare(
                        left.codePoints[index],
                        right.codePoints[index]
                );
                if (comparison != 0) {
                    return comparison;
                }
            }
            return Integer.compare(
                    left.codePoints.length,
                    right.codePoints.length
            );
        };
    }

    static final class Node {
        private final String terminal;
        private final PersistentAvlMap<Integer, Node> children;

        private Node(
                String terminal,
                PersistentAvlMap<Integer, Node> children
        ) {
            this.terminal = terminal;
            this.children = children;
        }

        private static Node empty() {
            return new Node(null, PersistentAvlMap.empty());
        }
    }

    private static final class TraversalWorkspace {
        private final int rowLength;
        private int[][] rows = new int[8][];

        private TraversalWorkspace(int rowLength) {
            this.rowLength = rowLength;
        }

        private int[] row(int depth) {
            if (depth >= rows.length) {
                rows = Arrays.copyOf(rows, Math.max(depth + 1, rows.length * 2));
            }
            int[] row = rows[depth];
            if (row == null) {
                row = new int[rowLength];
                rows[depth] = row;
            }
            return row;
        }
    }
}
