package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.NavigableMap;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;
import io.github.patricklfdm.generalsearch.internal.index.ImmutableOverlayMap;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Param;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;

/**
 * Compares D3 immutable dictionary publication strategies under identical point-update
 * workloads. Full-copy maps are controls, not proposed production representations.
 */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@Warmup(iterations = 2, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class DictionaryStrategyBenchmark {
    @Param({"10000", "100000"})
    public int dictionarySize;

    @Param({"1", "10", "100", "1000"})
    public int dirtyEntryCount;

    @Param({"UPDATE", "REMOVE_RESTORE"})
    public String mutationMode;

    private ImmutableOverlayMap<Integer, Integer> overlay;
    private PersistentAvlMap<Integer, Integer> persistent;
    private Map<Integer, Integer> hashCopy;
    private NavigableMap<Integer, Integer> treeCopy;
    private Map<Integer, Integer> changesA;
    private Map<Integer, Integer> changesB;
    private Set<Integer> removedKeys;
    private boolean overlayToggle;
    private boolean persistentToggle;
    private boolean hashToggle;
    private boolean treeToggle;

    @Setup(Level.Trial)
    public void setUp() {
        if (dirtyEntryCount > dictionarySize) {
            throw new IllegalArgumentException("dirtyEntryCount exceeds dictionarySize");
        }
        Map<Integer, Integer> initial = new HashMap<>(dictionarySize);
        PersistentAvlMap<Integer, Integer> ordered = PersistentAvlMap.empty();
        for (int key = 0; key < dictionarySize; key++) {
            initial.put(key, key);
            ordered = ordered.with(key, key);
        }
        overlay = ImmutableOverlayMap.<Integer, Integer>empty()
                .withChanges(initial, Set.of());
        persistent = ordered;
        hashCopy = Map.copyOf(initial);
        treeCopy = Collections.unmodifiableNavigableMap(new TreeMap<>(initial));

        Map<Integer, Integer> first = new HashMap<>(dirtyEntryCount);
        Map<Integer, Integer> second = new HashMap<>(dirtyEntryCount);
        Set<Integer> removed = new HashSet<>(dirtyEntryCount);
        for (int key = 0; key < dirtyEntryCount; key++) {
            first.put(key, -key - 1);
            second.put(key, key);
            removed.add(key);
        }
        changesA = Map.copyOf(first);
        changesB = Map.copyOf(second);
        removedKeys = Set.copyOf(removed);
    }

    @Benchmark
    public int boundedOverlayPublishAndLookup() {
        overlayToggle = !overlayToggle;
        if ("REMOVE_RESTORE".equals(mutationMode) && overlayToggle) {
            overlay = overlay.withChanges(Map.of(), removedKeys);
        } else {
            overlay = overlay.withChanges(
                    overlayToggle ? changesA : changesB,
                    Set.of()
            );
        }
        return required(overlay.get(dictionarySize - 1));
    }

    @Benchmark
    public int persistentAvlPublishAndLookup() {
        persistentToggle = !persistentToggle;
        if ("REMOVE_RESTORE".equals(mutationMode) && persistentToggle) {
            for (Integer key : removedKeys) {
                persistent = persistent.without(key);
            }
        } else {
            for (Map.Entry<Integer, Integer> entry
                    : (persistentToggle ? changesA : changesB).entrySet()) {
                persistent = persistent.with(entry.getKey(), entry.getValue());
            }
        }
        return required(persistent.get(dictionarySize - 1));
    }

    @Benchmark
    public int fullHashCopyPublishAndLookup() {
        hashToggle = !hashToggle;
        Map<Integer, Integer> updated = new HashMap<>(hashCopy);
        if ("REMOVE_RESTORE".equals(mutationMode) && hashToggle) {
            removedKeys.forEach(updated::remove);
        } else {
            updated.putAll(hashToggle ? changesA : changesB);
        }
        hashCopy = Map.copyOf(updated);
        return required(hashCopy.get(dictionarySize - 1));
    }

    @Benchmark
    public int fullTreeCopyPublishAndLookup() {
        treeToggle = !treeToggle;
        TreeMap<Integer, Integer> updated = new TreeMap<>(treeCopy);
        if ("REMOVE_RESTORE".equals(mutationMode) && treeToggle) {
            removedKeys.forEach(updated::remove);
        } else {
            updated.putAll(treeToggle ? changesA : changesB);
        }
        treeCopy = Collections.unmodifiableNavigableMap(updated);
        return required(treeCopy.get(dictionarySize - 1));
    }

    private int required(Integer value) {
        if (value == null) {
            throw new IllegalStateException("benchmark lookup unexpectedly missed");
        }
        return value;
    }
}
