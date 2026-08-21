package org.example.generalsearch.index;

import java.util.EnumMap;
import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.bitmap.ImmutableBitmapBuilder;
import org.example.generalsearch.model.Category;

public final class CategoryIndexBuilder {
    private final CategoryIndexSnapshot base;
    private final EnumMap<Category, ImmutableBitmapBuilder> dirty = new EnumMap<>(Category.class);
    private boolean built;

    public CategoryIndexBuilder(CategoryIndexSnapshot base) {
        this.base = Objects.requireNonNull(base, "base");
    }

    public void add(Category category, int docId) {
        builderFor(category).set(docId);
    }

    public void remove(Category category, int docId) {
        builderFor(category).clear(docId);
    }

    public void update(Category oldCategory, Category newCategory, int docId) {
        ensureOpen();
        if (oldCategory != newCategory) {
            remove(oldCategory, docId);
            add(newCategory, docId);
        }
    }

    public CategoryIndexSnapshot build() {
        ensureOpen();
        EnumMap<Category, ImmutableBitmap> updated = base.copyIndex();
        dirty.forEach((category, builder) -> {
            ImmutableBitmap bitmap = builder.build();
            if (bitmap.isEmpty()) {
                updated.remove(category);
            } else {
                updated.put(category, bitmap);
            }
        });
        built = true;
        return new CategoryIndexSnapshot(updated);
    }

    private ImmutableBitmapBuilder builderFor(Category category) {
        ensureOpen();
        Objects.requireNonNull(category, "category");
        return dirty.computeIfAbsent(category,
                key -> new ImmutableBitmapBuilder(base.get(key)));
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
