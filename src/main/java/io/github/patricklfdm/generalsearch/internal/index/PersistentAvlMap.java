package io.github.patricklfdm.generalsearch.internal.index;

import java.util.Objects;
import java.util.function.BiConsumer;

/**
 * Internal immutable ordered dictionary using AVL path copying.
 *
 * <p>This type is public only so ordered index implementations in sibling packages can
 * share it. It is not part of the supported application API.</p>
 *
 * @param <K> naturally ordered key type
 * @param <V> value type
 */
public final class PersistentAvlMap<K extends Comparable<? super K>, V> {
    private final Node<K, V> root;

    private PersistentAvlMap(Node<K, V> root) {
        this.root = root;
    }

    /** Returns an empty immutable ordered dictionary. */
    public static <K extends Comparable<? super K>, V> PersistentAvlMap<K, V> empty() {
        return new PersistentAvlMap<>(null);
    }

    /** Returns the value for {@code key}, or {@code null} when absent. */
    public V get(K key) {
        Objects.requireNonNull(key, "key");
        Node<K, V> current = root;
        while (current != null) {
            int comparison = key.compareTo(current.key);
            if (comparison == 0) {
                return current.value;
            }
            current = comparison < 0 ? current.left : current.right;
        }
        return null;
    }

    /** Returns the number of entries. */
    public int size() {
        return size(root);
    }

    /** Returns the AVL height for diagnostics and balance tests. */
    public int height() {
        return height(root);
    }

    /** Returns a dictionary with {@code key} associated with {@code value}. */
    public PersistentAvlMap<K, V> with(K key, V value) {
        Objects.requireNonNull(key, "key");
        Objects.requireNonNull(value, "value");
        Node<K, V> updated = put(root, key, value);
        return updated == root ? this : new PersistentAvlMap<>(updated);
    }

    /** Returns a dictionary without {@code key}. */
    public PersistentAvlMap<K, V> without(K key) {
        Objects.requireNonNull(key, "key");
        Node<K, V> updated = remove(root, key);
        return updated == root ? this : new PersistentAvlMap<>(updated);
    }

    /**
     * Visits entries in ascending key order between optional lower and upper bounds.
     * A {@code null} bound means unbounded on that side.
     */
    public void forEachInRange(
            K lowerBound,
            boolean lowerInclusive,
            K upperBound,
            boolean upperInclusive,
            BiConsumer<? super K, ? super V> consumer
    ) {
        Objects.requireNonNull(consumer, "consumer");
        visit(root, lowerBound, lowerInclusive, upperBound, upperInclusive, consumer);
    }

    private Node<K, V> put(Node<K, V> node, K key, V value) {
        if (node == null) {
            return new Node<>(key, value, null, null);
        }
        int comparison = key.compareTo(node.key);
        if (comparison == 0) {
            return Objects.equals(node.value, value)
                    ? node
                    : new Node<>(node.key, value, node.left, node.right);
        }
        Node<K, V> updatedChild = comparison < 0
                ? put(node.left, key, value)
                : put(node.right, key, value);
        if (updatedChild == (comparison < 0 ? node.left : node.right)) {
            return node;
        }
        return comparison < 0
                ? balance(new Node<>(node.key, node.value, updatedChild, node.right))
                : balance(new Node<>(node.key, node.value, node.left, updatedChild));
    }

    private Node<K, V> remove(Node<K, V> node, K key) {
        if (node == null) {
            return null;
        }
        int comparison = key.compareTo(node.key);
        if (comparison < 0) {
            Node<K, V> updatedLeft = remove(node.left, key);
            return updatedLeft == node.left
                    ? node
                    : balance(new Node<>(node.key, node.value, updatedLeft, node.right));
        }
        if (comparison > 0) {
            Node<K, V> updatedRight = remove(node.right, key);
            return updatedRight == node.right
                    ? node
                    : balance(new Node<>(node.key, node.value, node.left, updatedRight));
        }
        if (node.left == null) {
            return node.right;
        }
        if (node.right == null) {
            return node.left;
        }
        Node<K, V> successor = minimum(node.right);
        return balance(new Node<>(
                successor.key,
                successor.value,
                node.left,
                removeMinimum(node.right)
        ));
    }

    private Node<K, V> removeMinimum(Node<K, V> node) {
        if (node.left == null) {
            return node.right;
        }
        return balance(new Node<>(
                node.key,
                node.value,
                removeMinimum(node.left),
                node.right
        ));
    }

    private Node<K, V> minimum(Node<K, V> node) {
        Node<K, V> current = node;
        while (current.left != null) {
            current = current.left;
        }
        return current;
    }

    private Node<K, V> balance(Node<K, V> node) {
        int balance = height(node.left) - height(node.right);
        if (balance > 1) {
            Node<K, V> left = node.left;
            if (height(left.left) < height(left.right)) {
                left = rotateLeft(left);
            }
            return rotateRight(new Node<>(node.key, node.value, left, node.right));
        }
        if (balance < -1) {
            Node<K, V> right = node.right;
            if (height(right.right) < height(right.left)) {
                right = rotateRight(right);
            }
            return rotateLeft(new Node<>(node.key, node.value, node.left, right));
        }
        return node;
    }

    private Node<K, V> rotateLeft(Node<K, V> node) {
        Node<K, V> pivot = node.right;
        Node<K, V> moved = new Node<>(node.key, node.value, node.left, pivot.left);
        return new Node<>(pivot.key, pivot.value, moved, pivot.right);
    }

    private Node<K, V> rotateRight(Node<K, V> node) {
        Node<K, V> pivot = node.left;
        Node<K, V> moved = new Node<>(node.key, node.value, pivot.right, node.right);
        return new Node<>(pivot.key, pivot.value, pivot.left, moved);
    }

    private void visit(
            Node<K, V> node,
            K lowerBound,
            boolean lowerInclusive,
            K upperBound,
            boolean upperInclusive,
            BiConsumer<? super K, ? super V> consumer
    ) {
        if (node == null) {
            return;
        }
        boolean aboveLower = lowerBound == null
                || node.key.compareTo(lowerBound) > 0
                || lowerInclusive && node.key.compareTo(lowerBound) == 0;
        boolean belowUpper = upperBound == null
                || node.key.compareTo(upperBound) < 0
                || upperInclusive && node.key.compareTo(upperBound) == 0;

        if (lowerBound == null || node.key.compareTo(lowerBound) > 0) {
            visit(node.left, lowerBound, lowerInclusive,
                    upperBound, upperInclusive, consumer);
        }
        if (aboveLower && belowUpper) {
            consumer.accept(node.key, node.value);
        }
        if (upperBound == null || node.key.compareTo(upperBound) < 0) {
            visit(node.right, lowerBound, lowerInclusive,
                    upperBound, upperInclusive, consumer);
        }
    }

    private static int height(Node<?, ?> node) {
        return node == null ? 0 : node.height;
    }

    private static int size(Node<?, ?> node) {
        return node == null ? 0 : node.size;
    }

    private static final class Node<K, V> {
        private final K key;
        private final V value;
        private final Node<K, V> left;
        private final Node<K, V> right;
        private final int height;
        private final int size;

        private Node(K key, V value, Node<K, V> left, Node<K, V> right) {
            this.key = key;
            this.value = value;
            this.left = left;
            this.right = right;
            this.height = Math.max(PersistentAvlMap.height(left),
                    PersistentAvlMap.height(right)) + 1;
            this.size = Math.addExact(Math.addExact(
                    PersistentAvlMap.size(left),
                    PersistentAvlMap.size(right)
            ), 1);
        }
    }
}
