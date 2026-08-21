package org.example.generalsearch.engine.mutation;

import java.util.Objects;

public record SearchMutation<K, T>(Type type, K id, T document) {
    public enum Type {
        ADD,
        UPDATE,
        REMOVE
    }

    public SearchMutation {
        Objects.requireNonNull(type, "type");
        switch (type) {
            case ADD, UPDATE -> Objects.requireNonNull(document, "document");
            case REMOVE -> Objects.requireNonNull(id, "id");
        }
    }

    public static <K, T> SearchMutation<K, T> add(T document) {
        return new SearchMutation<>(Type.ADD, null, document);
    }

    public static <K, T> SearchMutation<K, T> update(T document) {
        return new SearchMutation<>(Type.UPDATE, null, document);
    }

    public static <K, T> SearchMutation<K, T> remove(K id) {
        return new SearchMutation<>(Type.REMOVE, id, null);
    }
}
