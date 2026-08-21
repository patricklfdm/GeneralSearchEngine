package org.example.generalsearch.index;

import java.util.Collections;
import java.util.NavigableMap;
import java.util.TreeMap;
import org.example.generalsearch.bitmap.ImmutableBitmap;

public final class PriceIndexSnapshot {
    private final NavigableMap<Double, ImmutableBitmap> index;

    public PriceIndexSnapshot() {
        this(new TreeMap<>());
    }

    PriceIndexSnapshot(NavigableMap<Double, ImmutableBitmap> index) {
        this.index = Collections.unmodifiableNavigableMap(index);
    }

    public ImmutableBitmap get(double price) {
        return index.getOrDefault(price, ImmutableBitmap.empty());
    }

    public ImmutableBitmap getByRange(double minPrice, double maxPrice) {
        if (Double.compare(minPrice, maxPrice) > 0) {
            return ImmutableBitmap.empty();
        }
        ImmutableBitmap result = ImmutableBitmap.empty();
        for (ImmutableBitmap bitmap : index.subMap(minPrice, true, maxPrice, true).values()) {
            result = result.or(bitmap);
        }
        return result;
    }

    TreeMap<Double, ImmutableBitmap> copyIndex() {
        return new TreeMap<>(index);
    }
}
