package io.github.patricklfdm.generalsearch.benchmark.jmh;

import java.util.Collections;
import java.util.HashMap;
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

/** Compares D3 point lookup at a compacted root and the maximum overlay depth. */
@BenchmarkMode(Mode.AverageTime)
@OutputTimeUnit(TimeUnit.NANOSECONDS)
@Warmup(iterations = 3, time = 1)
@Measurement(iterations = 5, time = 1)
@Fork(2)
@State(Scope.Benchmark)
public class DictionaryLookupBenchmark {
    @Param({"10000", "100000"})
    public int dictionarySize;

    @Param({"0", "12"})
    public int overlayDepth;

    private ImmutableOverlayMap<Integer, Integer> overlay;
    private PersistentAvlMap<Integer, Integer> persistent;
    private Map<Integer, Integer> hash;
    private NavigableMap<Integer, Integer> tree;
    private int lookupKey;

    @Setup(Level.Trial)
    public void setUp() {
        Map<Integer, Integer> initial = new HashMap<>(dictionarySize);
        PersistentAvlMap<Integer, Integer> ordered = PersistentAvlMap.empty();
        for (int key = 0; key < dictionarySize; key++) {
            initial.put(key, key);
            ordered = ordered.with(key, key);
        }
        overlay = ImmutableOverlayMap.<Integer, Integer>empty()
                .withChanges(initial, Set.of());
        Map<Integer, Integer> updated = new HashMap<>(initial);
        for (int layer = 0; layer < overlayDepth; layer++) {
            int value = -layer - 1;
            overlay = overlay.withChanges(Map.of(layer, value), Set.of());
            ordered = ordered.with(layer, value);
            updated.put(layer, value);
        }
        if (overlay.depth() != overlayDepth) {
            throw new IllegalStateException(
                    "unexpected overlay depth: " + overlay.depth());
        }
        persistent = ordered;
        hash = Map.copyOf(updated);
        tree = Collections.unmodifiableNavigableMap(new TreeMap<>(updated));
        lookupKey = dictionarySize - 1;
    }

    @Benchmark
    public int boundedOverlayLookup() {
        return required(overlay.get(lookupKey));
    }

    @Benchmark
    public int persistentAvlLookup() {
        return required(persistent.get(lookupKey));
    }

    @Benchmark
    public int immutableHashLookup() {
        return required(hash.get(lookupKey));
    }

    @Benchmark
    public int immutableTreeLookup() {
        return required(tree.get(lookupKey));
    }

    private int required(Integer value) {
        if (value == null) {
            throw new IllegalStateException("benchmark lookup unexpectedly missed");
        }
        return value;
    }
}
