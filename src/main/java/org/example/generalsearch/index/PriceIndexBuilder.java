package org.example.generalsearch.index;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.bitmap.ImmutableBitmapBuilder;

public final class PriceIndexBuilder {
    private final PriceIndexSnapshot base;
    private final Map<Double, ImmutableBitmapBuilder> dirty = new HashMap<>();
    private boolean built;

    public PriceIndexBuilder(PriceIndexSnapshot base) {
        this.base = Objects.requireNonNull(base, "base");
    }

    public void add(double price, int docId) {
        builderFor(price).set(docId);
    }

    public void remove(double price, int docId) {
        builderFor(price).clear(docId);
    }

    public void update(double oldPrice, double newPrice, int docId) {
        ensureOpen();
        if (Double.compare(oldPrice, newPrice) != 0) {
            remove(oldPrice, docId);
            add(newPrice, docId);
        }
    }

    public PriceIndexSnapshot build() {
        ensureOpen();
        TreeMap<Double, ImmutableBitmap> updated = base.copyIndex();
        dirty.forEach((price, builder) -> {
            ImmutableBitmap bitmap = builder.build();
            if (bitmap.isEmpty()) {
                updated.remove(price);
            } else {
                updated.put(price, bitmap);
            }
        });
        built = true;
        return new PriceIndexSnapshot(updated);
    }

    private ImmutableBitmapBuilder builderFor(double price) {
        ensureOpen();
        return dirty.computeIfAbsent(price,
                key -> new ImmutableBitmapBuilder(base.get(key)));
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
