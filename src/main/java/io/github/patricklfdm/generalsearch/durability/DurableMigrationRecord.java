package io.github.patricklfdm.generalsearch.durability;

import java.util.Objects;

/** One non-null target key/document pair produced by a migration transform. */
public record DurableMigrationRecord<K, T>(K key, T document) {
    public DurableMigrationRecord {
        Objects.requireNonNull(key, "key");
        Objects.requireNonNull(document, "document");
    }
}
