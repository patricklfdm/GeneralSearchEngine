package io.github.patricklfdm.generalsearch.index.prefix;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.schema.Field;

public final class PrefixIndexBuilder<T> implements IndexBuilder<T> {
    private final PrefixIndexSnapshot<T> base;
    private final Field<T, String> field;
    private final Map<String, ImmutableBitmapBuilder> dirty = new HashMap<>();
    private int indexedDocumentCount;
    private boolean built;

    public PrefixIndexBuilder(PrefixIndexSnapshot<T> base) {
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
        String oldValue = field.valueOf(oldDocument);
        String newValue = field.valueOf(newDocument);
        if (!Objects.equals(oldValue, newValue)) {
            removeValue(oldValue, docId);
            addValue(newValue, docId);
        }
    }

    @Override
    public IndexSnapshot<T> build() {
        ensureOpen();
        TreeMap<String, ImmutableBitmap> values = base.copyValues();
        dirty.forEach((value, builder) -> {
            ImmutableBitmap bitmap = builder.build();
            if (bitmap.isEmpty()) {
                values.remove(value);
            } else {
                values.put(value, bitmap);
            }
        });
        built = true;
        return PrefixIndexSnapshot.fromOwnedValues(
                field,
                values,
                indexedDocumentCount
        );
    }

    private void addValue(String value, int docId) {
        if (value != null) {
            ImmutableBitmapBuilder builder = builderFor(value);
            if (!builder.get(docId)) {
                builder.set(docId);
                indexedDocumentCount++;
            }
        }
    }

    private void removeValue(String value, int docId) {
        if (value != null) {
            ImmutableBitmapBuilder builder = builderFor(value);
            if (builder.get(docId)) {
                builder.clear(docId);
                indexedDocumentCount--;
            }
        }
    }

    private ImmutableBitmapBuilder builderFor(String value) {
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
