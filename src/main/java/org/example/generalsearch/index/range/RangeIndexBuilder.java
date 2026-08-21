package org.example.generalsearch.index.range;

import java.util.Objects;
import java.util.TreeMap;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.bitmap.ImmutableBitmapBuilder;
import org.example.generalsearch.index.IndexBuilder;
import org.example.generalsearch.index.IndexSnapshot;
import org.example.generalsearch.schema.Field;

public final class RangeIndexBuilder<T, V extends Comparable<? super V>>
        implements IndexBuilder<T> {
    private final RangeIndexSnapshot<T, V> base;
    private final Field<T, V> field;
    // Range keys use compareTo identity, just like the snapshot's TreeMap. A HashMap
    // would split values such as BigDecimal("1.0") and BigDecimal("1.00") even though
    // they occupy one natural-order bucket.
    private final TreeMap<V, ImmutableBitmapBuilder> dirty = new TreeMap<>();
    private boolean built;

    public RangeIndexBuilder(RangeIndexSnapshot<T, V> base) {
        this.base = Objects.requireNonNull(base, "base");
        this.field = base.field();
    }

    @Override
    public void add(int docId, T document) {
        ensureOpen();
        addValue(field.valueOf(document), docId);
    }

    @Override
    public void remove(int docId, T document) {
        ensureOpen();
        removeValue(field.valueOf(document), docId);
    }

    @Override
    public void update(int docId, T oldDocument, T newDocument) {
        ensureOpen();
        V oldValue = field.valueOf(oldDocument);
        V newValue = field.valueOf(newDocument);
        if (!Objects.equals(oldValue, newValue)) {
            removeValue(oldValue, docId);
            addValue(newValue, docId);
        }
    }

    @Override
    public IndexSnapshot<T> build() {
        ensureOpen();
        TreeMap<V, ImmutableBitmap> values = base.copyValues();
        dirty.forEach((value, builder) -> {
            ImmutableBitmap bitmap = builder.build();
            if (bitmap.isEmpty()) {
                values.remove(value);
            } else {
                values.put(value, bitmap);
            }
        });
        built = true;
        return RangeIndexSnapshot.fromOwnedValues(field, values);
    }

    private void addValue(V value, int docId) {
        if (value != null) {
            builderFor(value).set(docId);
        }
    }

    private void removeValue(V value, int docId) {
        if (value != null) {
            builderFor(value).clear(docId);
        }
    }

    private ImmutableBitmapBuilder builderFor(V value) {
        return dirty.computeIfAbsent(
                value,
                key -> new ImmutableBitmapBuilder(base.get(key))
        );
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
