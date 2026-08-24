package io.github.patricklfdm.generalsearch.internal.index;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Internal immutable hash dictionary backed by a bounded chain of dirty overlays.
 *
 * <p>This type is public only so index implementations in sibling packages can share
 * it. It is not part of the supported application API.</p>
 *
 * @param <K> key type
 * @param <V> value type
 */
public final class ImmutableOverlayMap<K, V> {
    private static final int MAX_DEPTH = 12;
    private static final int MIN_EAGER_COMPACTION_CHANGES = 64;

    private final ImmutableOverlayMap<K, V> parent;
    private final Map<K, V> rootValues;
    private final Map<K, V> replacements;
    private final Set<K> removals;
    private final int size;
    private final int depth;

    private ImmutableOverlayMap(Map<K, V> rootValues) {
        this.parent = null;
        this.rootValues = Map.copyOf(rootValues);
        this.replacements = Map.of();
        this.removals = Set.of();
        this.size = this.rootValues.size();
        this.depth = 0;
    }

    private ImmutableOverlayMap(
            ImmutableOverlayMap<K, V> parent,
            Map<K, V> replacements,
            Set<K> removals,
            int size
    ) {
        this.parent = parent;
        this.rootValues = Map.of();
        this.replacements = Map.copyOf(replacements);
        this.removals = Set.copyOf(removals);
        this.size = size;
        this.depth = parent.depth + 1;
    }

    /** Returns an empty immutable dictionary. */
    public static <K, V> ImmutableOverlayMap<K, V> empty() {
        return new ImmutableOverlayMap<>(Map.of());
    }

    /** Returns the value for {@code key}, or {@code null} when it is absent. */
    public V get(K key) {
        Objects.requireNonNull(key, "key");
        ImmutableOverlayMap<K, V> current = this;
        while (current.parent != null) {
            V replacement = current.replacements.get(key);
            if (replacement != null) {
                return replacement;
            }
            if (current.removals.contains(key)) {
                return null;
            }
            current = current.parent;
        }
        return current.rootValues.get(key);
    }

    /** Returns whether {@code key} is present. */
    public boolean containsKey(K key) {
        return get(key) != null;
    }

    /** Returns the number of current entries. */
    public int size() {
        return size;
    }

    /** Returns the current overlay depth for diagnostics and boundedness tests. */
    public int depth() {
        return depth;
    }

    /**
     * Returns a dictionary containing the supplied replacements and removals.
     * Ineffective changes are discarded, and large or deep overlays are compacted.
     */
    public ImmutableOverlayMap<K, V> withChanges(
            Map<? extends K, ? extends V> requestedReplacements,
            Set<? extends K> requestedRemovals
    ) {
        Objects.requireNonNull(requestedReplacements, "requestedReplacements");
        Objects.requireNonNull(requestedRemovals, "requestedRemovals");

        Map<K, V> effectiveReplacements = new HashMap<>();
        for (Map.Entry<? extends K, ? extends V> entry
                : requestedReplacements.entrySet()) {
            K key = Objects.requireNonNull(entry.getKey(), "replacement key");
            V value = Objects.requireNonNull(entry.getValue(), "replacement value");
            if (requestedRemovals.contains(key)) {
                throw new IllegalArgumentException("a key cannot be replaced and removed");
            }
            if (!Objects.equals(get(key), value)) {
                effectiveReplacements.put(key, value);
            }
        }

        Set<K> effectiveRemovals = new java.util.HashSet<>();
        for (K key : requestedRemovals) {
            Objects.requireNonNull(key, "removed key");
            if (containsKey(key)) {
                effectiveRemovals.add(key);
            }
        }
        if (effectiveReplacements.isEmpty() && effectiveRemovals.isEmpty()) {
            return this;
        }

        int updatedSize = size;
        for (K key : effectiveReplacements.keySet()) {
            if (!containsKey(key)) {
                updatedSize++;
            }
        }
        updatedSize -= effectiveRemovals.size();

        ImmutableOverlayMap<K, V> updated = new ImmutableOverlayMap<>(
                this,
                effectiveReplacements,
                effectiveRemovals,
                updatedSize
        );
        int changedEntries = effectiveReplacements.size() + effectiveRemovals.size();
        int compactionThreshold = Math.max(
                MIN_EAGER_COMPACTION_CHANGES,
                Math.max(1, size / 4)
        );
        return updated.depth > MAX_DEPTH || changedEntries >= compactionThreshold
                ? updated.compact()
                : updated;
    }

    private ImmutableOverlayMap<K, V> compact() {
        List<ImmutableOverlayMap<K, V>> layers = new ArrayList<>(depth);
        ImmutableOverlayMap<K, V> current = this;
        while (current.parent != null) {
            layers.add(current);
            current = current.parent;
        }
        Map<K, V> flattened = new HashMap<>(current.rootValues);
        for (int index = layers.size() - 1; index >= 0; index--) {
            ImmutableOverlayMap<K, V> layer = layers.get(index);
            layer.removals.forEach(flattened::remove);
            flattened.putAll(layer.replacements);
        }
        return new ImmutableOverlayMap<>(flattened);
    }

}
