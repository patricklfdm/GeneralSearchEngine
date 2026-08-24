package io.github.patricklfdm.generalsearch.index.equality;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.internal.index.ImmutableOverlayMap;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class EqualityIndexBuilder<T, V> implements IndexBuilder<T> {
    private final EqualityIndexSnapshot<T, V> base;
    private final Field<T, V> field;
    private final Map<V, ImmutableBitmapBuilder> dirty = new HashMap<>();
    private int indexedDocumentCount;
    private boolean built;

    public EqualityIndexBuilder(EqualityIndexSnapshot<T, V> base) {
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
        Map<V, ImmutableBitmap> replacements = new HashMap<>();
        Set<V> removals = new HashSet<>();
        dirty.forEach((value, builder) -> {
            ImmutableBitmap bitmap = builder.build();
            if (bitmap.isEmpty()) {
                removals.add(value);
            } else {
                replacements.put(value, bitmap);
            }
        });
        ImmutableOverlayMap<V, ImmutableBitmap> values =
                base.values().withChanges(replacements, removals);
        built = true;
        if (values == base.values()
                && indexedDocumentCount == base.statistics().indexedDocumentCount()) {
            return base;
        }
        return EqualityIndexSnapshot.fromValues(
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
