package io.github.patricklfdm.generalsearch.index;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public final class IndexRegistryBuilder<T> {
    private final List<IndexBuilder<T>> builders;
    private boolean built;

    public IndexRegistryBuilder(IndexRegistry<T> base) {
        Objects.requireNonNull(base, "base");
        this.builders = base.indexes().stream()
                .map(IndexSnapshot::toBuilder)
                .toList();
    }

    public void add(int docId, T document) {
        ensureOpen();
        builders.forEach(builder -> builder.add(docId, document));
    }

    public void remove(int docId, T document) {
        ensureOpen();
        builders.forEach(builder -> builder.remove(docId, document));
    }

    public void update(int docId, T oldDocument, T newDocument) {
        ensureOpen();
        builders.forEach(builder -> builder.update(docId, oldDocument, newDocument));
    }

    public IndexRegistry<T> build() {
        ensureOpen();
        List<IndexSnapshot<T>> indexes = new ArrayList<>(builders.size());
        builders.forEach(builder -> indexes.add(builder.build()));
        built = true;
        return IndexRegistry.fromSnapshots(indexes);
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
