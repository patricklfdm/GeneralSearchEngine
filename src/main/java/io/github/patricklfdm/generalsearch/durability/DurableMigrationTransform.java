package io.github.patricklfdm.generalsearch.durability;

/** Deterministic one-to-one transform used by an offline durable migration. */
@FunctionalInterface
public interface DurableMigrationTransform<SK, ST, TK, TT> {
    /** Transforms one source business key and document into one target record. */
    DurableMigrationRecord<TK, TT> transform(SK sourceKey, ST sourceDocument);
}
