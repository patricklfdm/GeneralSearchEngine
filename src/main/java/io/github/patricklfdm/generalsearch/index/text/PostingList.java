package io.github.patricklfdm.generalsearch.index.text;

import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;

/** Immutable term membership and per-document occurrence facts retained for scoring. */
public final class PostingList {
    private final ImmutableBitmap documents;
    private final PersistentAvlMap<Integer, IntPositions> positionsByDocument;

    private PostingList(
            ImmutableBitmap documents,
            PersistentAvlMap<Integer, IntPositions> positionsByDocument
    ) {
        this.documents = Objects.requireNonNull(documents, "documents");
        this.positionsByDocument = Objects.requireNonNull(
                positionsByDocument, "positionsByDocument");
    }

    public static PostingList empty() {
        return new PostingList(ImmutableBitmap.empty(), PersistentAvlMap.empty());
    }

    static PostingList fromPositions(Map<Integer, int[]> positionsByDocument) {
        Objects.requireNonNull(positionsByDocument, "positionsByDocument");
        ImmutableBitmapBuilder documents = new ImmutableBitmapBuilder(
                ImmutableBitmap.empty());
        PersistentAvlMap<Integer, IntPositions> positions =
                PersistentAvlMap.empty();
        for (var entry : new TreeMap<>(positionsByDocument).entrySet()) {
            int docId = Objects.requireNonNull(entry.getKey(), "document ID");
            if (docId < 0) {
                throw new IllegalArgumentException(
                        "document IDs must not be negative");
            }
            IntPositions value = IntPositions.copyOf(Objects.requireNonNull(
                    entry.getValue(), "positions"));
            if (value.size() == 0) {
                throw new IllegalArgumentException(
                        "persisted positions must not be empty");
            }
            documents.set(docId);
            positions = positions.with(docId, value);
        }
        return new PostingList(documents.build(), positions);
    }

    public ImmutableBitmap documents() {
        return documents;
    }

    public int documentFrequency() {
        return documents.cardinality();
    }

    public int termFrequency(int docId) {
        return positions(docId).size();
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
        return withPositions(docId, IntPositions.sequential(frequency));
    }

    PostingList withPositions(int docId, IntPositions positions) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
        Objects.requireNonNull(positions, "positions");
        if (positions.size() == 0) {
            throw new IllegalArgumentException("positions must not be empty");
        }
        if (positions.equals(positions(docId))) {
            return this;
        }
        return new PostingList(
                documents.withSet(docId),
                positionsByDocument.with(docId, positions)
        );
    }

    IntPositions positions(int docId) {
        IntPositions positions = positionsByDocument.get(docId);
        return positions == null ? IntPositions.empty() : positions;
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
                positionsByDocument.without(docId)
        );
    }
}
