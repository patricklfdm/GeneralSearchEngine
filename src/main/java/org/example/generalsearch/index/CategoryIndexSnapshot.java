package org.example.generalsearch.index;

import java.util.EnumMap;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.model.Category;

public final class CategoryIndexSnapshot {
    private final EnumMap<Category, ImmutableBitmap> index;

    public CategoryIndexSnapshot() {
        this(new EnumMap<>(Category.class));
    }

    CategoryIndexSnapshot(EnumMap<Category, ImmutableBitmap> index) {
        this.index = index;
    }

    public ImmutableBitmap get(Category category) {
        return index.getOrDefault(category, ImmutableBitmap.empty());
    }

    EnumMap<Category, ImmutableBitmap> copyIndex() {
        return new EnumMap<>(index);
    }
}
