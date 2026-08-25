package io.github.patricklfdm.generalsearch.index.text;

import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;

/** Immutable term membership and per-document frequency retained for P5 scoring. */
public final class PostingList {
    private final ImmutableBitmap documents;
    private final PersistentAvlMap<Integer, Integer> termFrequencies;

    private PostingList(
            ImmutableBitmap documents,
            PersistentAvlMap<Integer, Integer> termFrequencies
    ) {
        this.documents = documents;
        this.termFrequencies = termFrequencies;
    }

    public static PostingList empty() {
        return new PostingList(ImmutableBitmap.empty(), PersistentAvlMap.empty());
    }

    public ImmutableBitmap documents() {
        return documents;
    }

    public int documentFrequency() {
        return documents.cardinality();
    }

    public int termFrequency(int docId) {
        Integer frequency = termFrequencies.get(docId);
        return frequency == null ? 0 : frequency;
    }

    public PostingList withTermFrequency(int docId, int frequency) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
        if (frequency <= 0) {
            throw new IllegalArgumentException("frequency must be positive");
        }
        if (termFrequency(docId) == frequency) {
            return this;
        }
        return new PostingList(
                documents.withSet(docId),
                termFrequencies.with(docId, frequency)
        );
    }

    public PostingList without(int docId) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
        if (!documents.get(docId)) {
            return this;
        }
        return new PostingList(
                documents.withClear(docId),
                termFrequencies.without(docId)
        );
    }
}
