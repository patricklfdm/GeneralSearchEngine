package io.github.patricklfdm.generalsearch.index.range;

import java.util.Objects;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class RangeIndexBuilder<T, V extends Comparable<? super V>>
        implements IndexBuilder<T> {
    private final RangeIndexSnapshot<T, V> base;
    private final Field<T, V> field;
    // Range keys use compareTo identity, just like the snapshot's TreeMap. A HashMap
    // would split values such as BigDecimal("1.0") and BigDecimal("1.00") even though
    // they occupy one natural-order bucket.
    private final TreeMap<V, ImmutableBitmapBuilder> dirty = new TreeMap<>();
    private int indexedDocumentCount;
    private boolean built;

    public RangeIndexBuilder(RangeIndexSnapshot<T, V> base) {
        this.base = Objects.requireNonNull(base, "base");
        this.field = base.field();
        this.indexedDocumentCount = base.statistics().indexedDocumentCount();
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
        if (dirty.isEmpty()) {
            built = true;
            return base;
        }
        PersistentAvlMap<V, ImmutableBitmap> values = base.values();
        for (var entry : dirty.entrySet()) {
            V value = entry.getKey();
            ImmutableBitmap bitmap = entry.getValue().build();
            if (bitmap.isEmpty()) {
                values = values.without(value);
            } else {
                values = values.with(value, bitmap);
            }
        }
        built = true;
        if (values == base.values()
                && indexedDocumentCount == base.statistics().indexedDocumentCount()) {
            return base;
        }
        return RangeIndexSnapshot.fromValues(
                field,
                values,
                indexedDocumentCount
        );
    }

    private void addValue(V value, int docId) {
        if (value != null) {
            ImmutableBitmapBuilder builder = builderFor(value);
            if (!builder.get(docId)) {
                builder.set(docId);
                indexedDocumentCount++;
            }
        }
    }

    private void removeValue(V value, int docId) {
        if (value != null) {
            ImmutableBitmapBuilder builder = builderFor(value);
            if (builder.get(docId)) {
                builder.clear(docId);
                indexedDocumentCount--;
            }
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
